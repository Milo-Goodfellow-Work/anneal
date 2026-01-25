"""
Anneal Stages - Differential testing implementation.

This module contains the procedural differential test runner.

Differential testing works by:
1. Generating test inputs (commands) via gen_inputs.py
2. Feeding the SAME inputs to both the C harness and Lean harness
3. Comparing their stdout - they must be byte-for-byte identical

Both programs run independently and receive identical stdin.
"""
from __future__ import annotations
import sys
import json
import time
import signal
import shlex
import subprocess
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime

from helpers import (
    log, trunc, trunc_tail, _safe_relpath, run_lake_build, run_lake_build_target,
    list_project_files, SPEC_DIR, SPEC_TESTS_DIR, SPEC_REPORTS_DIR,
    DIFF_REQUIRED_RUNS, DIFF_MIN_CASES_PER_RUN, DIFF_SEED_START, DIFF_MIN_OUTPUT_RATIO,
    GEN_TIMEOUT_S, C_RUN_TIMEOUT_S, LEAN_RUN_TIMEOUT_S,
)


def _save_trace(project_name: str, seed: int, inputs: str, c_out: str, lean_out: str, match: bool):
    """Save input/output pairs to a trace file for inspection."""
    trace_dir = SPEC_REPORTS_DIR
    trace_dir.mkdir(parents=True, exist_ok=True)
    trace_file = trace_dir / f"{project_name}_diff_trace.txt"
    
    # Parse into lines
    input_lines = [l for l in inputs.strip().split('\n') if l.strip()]
    c_lines = [l for l in c_out.strip().split('\n') if l.strip()]
    lean_lines = [l for l in lean_out.strip().split('\n') if l.strip()]
    
    with open(trace_file, 'a') as f:
        f.write(f"\n# Seed {seed} — {'PASS' if match else 'FAIL'}\n")
        
        # Match inputs to outputs line by line
        max_cases = max(len(input_lines), len(c_lines), len(lean_lines))
        for i in range(max_cases):
            inp = input_lines[i] if i < len(input_lines) else "(no input)"
            c = c_lines[i] if i < len(c_lines) else "(no output)"
            lean = lean_lines[i] if i < len(lean_lines) else "(no output)"
            ok = "✓" if c == lean else "✗"
            
            # Truncate long inputs for readability
            if len(inp) > 80:
                inp = inp[:77] + "..."
            
            f.write(f"{ok} | {inp} | C: {c} | Lean: {lean}\n")
    
    log(f"[DiffTest] Trace saved to {trace_file}")


def _normalize_lean_harness_relpath(p: str) -> str:
    """Normalize a harness path."""
    p = (p or "").replace("\\", "/").strip()
    if p.startswith("./"):
        p = p[2:]
    if p.startswith("spec/Spec/"):
        p = p[len("spec/Spec/"):]
    if p.startswith("Spec/"):
        p = p[len("Spec/"):]
    return _safe_relpath(p)


def run_differential_test_impl(ctx: dict, args: Dict[str, Any]) -> str:
    """
    Robust differential test runner.
    Returns JSON string with status + details.
    """
    gen_script = _safe_relpath(args.get("gen_script_path", "spec/tests/gen_inputs.py"))
    c_harness = _safe_relpath(args.get("c_harness_path", "spec/tests/harness.c"))
    source_harness = c_harness
    raw = args.get("lean_harness_path", "tests/Harness.lean")
    lean_harness = _normalize_lean_harness_relpath(raw)

    t0 = time.time()

    candidates = []
    candidates.append(ctx["spec_src_root"] / lean_harness)
    candidates.append(ctx["spec_src_root"] / "tests/Harness.lean")

    lean_run_path = None
    for cand in candidates:
        if cand.exists():
            lean_run_path = cand
            break

    if lean_run_path is None:
        tests_dir = ctx["spec_src_root"] / "tests"
        listing = []
        if tests_dir.exists():
            listing = sorted([x.name for x in tests_dir.iterdir() if x.is_file()])[:50]

        return json.dumps({
            "status": "error",
            "where": "lean_harness",
            "message": "Lean harness not found",
            "raw_arg": raw,
            "normalized": lean_harness,
            "tried": [str(c) for c in candidates],
            "tests_dir_listing": listing,
        })

    def _rc_desc(rc: int) -> str:
        if rc < 0:
            sig = -rc
            try:
                return f"signal {signal.Signals(sig).name} ({rc})"
            except Exception:
                return f"signal {sig} ({rc})"
        return str(rc)

    # 1) Compile Source Harness
    exe_source = SPEC_TESTS_DIR / "harness.exe"
    build_dir = SPEC_TESTS_DIR / "build"
    build_dir.mkdir(parents=True, exist_ok=True)

    if str(source_harness).endswith(".c"):
        proj_c_srcs = [
            (ctx["source_root"] / f)
            for f in list_project_files(ctx["source_root"])
            if f.endswith(".c") and "main.c" not in f.replace("\\", "/").lower()
        ]

        include_dirs = {str(ctx["source_root"].resolve())}
        for f in list_project_files(ctx["source_root"]):
            if f.endswith((".h", ".hpp")):
                include_dirs.add(str((ctx["source_root"] / Path(f).parent).resolve()))
        include_flags = [flag for d in sorted(include_dirs) for flag in ["-I", d]]

        COMMON = ["-std=c11", "-O2", "-g", "-fno-omit-frame-pointer"]

        HARNESS_C = str(Path(source_harness))
        harness_o = build_dir / "harness.o"
        harness_cmd = [
            "gcc", *COMMON,
            "-Wall", "-Wextra",
            "-Werror=implicit-function-declaration",
            "-Werror=return-type",
            *include_flags,
            "-c", HARNESS_C, "-o", str(harness_o),
        ]

        proj_macros: List[str] = []
        proj_os: List[Path] = []
        proj_compile_cmds: List[List[str]] = []
        for src in proj_c_srcs:
            obj = build_dir / (src.stem + ".o")
            proj_os.append(obj)
            proj_compile_cmds.append([
                "gcc", *COMMON,
                *proj_macros,
                *include_flags,
                "-c", str(src), "-o", str(obj),
            ])

        link_cmd = ["gcc", "-o", str(exe_source), str(harness_o)] + [str(o) for o in proj_os]

        proc_h = subprocess.run(harness_cmd, capture_output=True, text=True)
        if proc_h.returncode != 0:
            return json.dumps({
                "status": "error",
                "where": "source_compile",
                "message": "Harness compile failed",
                "cmd": " ".join(shlex.quote(x) for x in harness_cmd),
                "stderr": trunc(proc_h.stderr, 3000),
                "stdout": trunc(proc_h.stdout, 1500),
            })

        for cmd in proj_compile_cmds:
            proc_s = subprocess.run(cmd, capture_output=True, text=True)
            if proc_s.returncode != 0:
                return json.dumps({
                    "status": "error",
                    "where": "source_compile",
                    "message": "Project source compile failed",
                    "cmd": " ".join(shlex.quote(x) for x in cmd),
                    "stderr": trunc(proc_s.stderr, 3000),
                    "stdout": trunc(proc_s.stdout, 1500),
                })

        proc_l = subprocess.run(link_cmd, capture_output=True, text=True)
        if proc_l.returncode != 0:
            return json.dumps({
                "status": "error",
                "where": "source_link",
                "message": "Link failed",
                "cmd": " ".join(shlex.quote(x) for x in link_cmd),
                "stderr": trunc(proc_l.stderr, 3000),
                "stdout": trunc(proc_l.stdout, 1500),
            })

    # 2) Ensure Lean builds
    log("[DiffTest] Starting lake build...")
    build_start = time.time()
    b_out = run_lake_build(ctx["spec_pkg_root"])
    log(f"[DiffTest] lake build completed in {time.time() - build_start:.1f}s")
    if not b_out.startswith("Build Success"):
        return json.dumps({"status": "error", "where": "lean_build", "message": "Lean build failed", "build": trunc(b_out, 4000)})

    log("[DiffTest] Building harness target Spec.tests.Harness...")
    harness_build_start = time.time()
    hb = run_lake_build_target(ctx["spec_pkg_root"], target="Spec.tests.Harness")
    log(f"[DiffTest] Harness build completed in {time.time() - harness_build_start:.1f}s")
    if not hb.startswith("Build Success"):
        return json.dumps({
            "status": "error",
            "where": "lean_harness_build",
            "message": "Lean harness does not typecheck",
            "build": trunc_tail(hb, 4000),
        })

    # 3) Run multiple seeds
    runs: List[Dict[str, Any]] = []
    passed = 0

    for k in range(DIFF_REQUIRED_RUNS):
        seed = DIFF_SEED_START + k

        try:
            gen_proc = subprocess.run(
                [sys.executable, gen_script, "--seed", str(seed), "--n", str(DIFF_MIN_CASES_PER_RUN)],
                capture_output=True,
                text=True,
                timeout=GEN_TIMEOUT_S,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return json.dumps({"status": "timeout", "where": "generator", "seed": seed, "message": f"gen_inputs.py exceeded {GEN_TIMEOUT_S}s"})
        except Exception as e:
            return json.dumps({"status": "error", "where": "generator", "seed": seed, "message": str(e)})

        if gen_proc.returncode != 0:
            return json.dumps({
                "status": "error",
                "where": "generator",
                "seed": seed,
                "message": "Generator must accept '--seed' and '--n' and exit 0.",
                "stderr": trunc(gen_proc.stderr, 2000),
                "stdout": trunc(gen_proc.stdout, 1200),
            })

        inputs = gen_proc.stdout
        lines = [ln for ln in inputs.splitlines() if ln.strip() != ""]
        num_cases = len(lines)

        if num_cases < DIFF_MIN_CASES_PER_RUN:
            return json.dumps({
                "status": "insufficient_tests",
                "where": "generator",
                "seed": seed,
                "message": f"Generator produced only {num_cases} cases; require >= {DIFF_MIN_CASES_PER_RUN}.",
            })

        # Run C
        log(f"[DiffTest] Running C harness (seed={seed}, {num_cases} cases)...")
        c_start = time.time()
        try:
            c_run = subprocess.run(
                [str(exe_source)],
                input=inputs,
                capture_output=True,
                text=True,
                timeout=C_RUN_TIMEOUT_S
            )
            c_out = c_run.stdout
            c_err = c_run.stderr
            c_rc = c_run.returncode
            log(f"[DiffTest] C harness done in {time.time() - c_start:.2f}s (rc={c_rc})")
        except subprocess.TimeoutExpired:
            return json.dumps({
                "status": "timeout",
                "where": "c_run",
                "seed": seed,
                "message": f"C harness exceeded {C_RUN_TIMEOUT_S}s",
                "inputs_tail": "\n".join(lines[-20:]),
            })
        except Exception as e:
            return json.dumps({
                "status": "error",
                "where": "c_run",
                "seed": seed,
                "message": str(e),
                "inputs_tail": "\n".join(lines[-20:]),
            })

        if c_rc != 0:
            return json.dumps({
                "status": "error",
                "where": "c_run",
                "seed": seed,
                "message": f"C harness exited {_rc_desc(c_rc)}",
                "inputs_tail": "\n".join(lines[-40:]),
                "stderr": trunc(c_err, 3000),
                "stdout": trunc(c_out, 3000),
            })

        # Run Lean
        log(f"[DiffTest] Running Lean harness (seed={seed})...")
        lean_start = time.time()
        try:
            lean_cmd = ["lake", "env", "lean", "--run", str(lean_run_path)]
            lean_run = subprocess.run(
                lean_cmd,
                cwd=str(ctx["spec_pkg_root"]),
                input=inputs,
                capture_output=True,
                text=True,
                timeout=LEAN_RUN_TIMEOUT_S,
            )
            lean_out = lean_run.stdout
            lean_err = lean_run.stderr
            lean_rc = lean_run.returncode
            log(f"[DiffTest] Lean harness done in {time.time() - lean_start:.2f}s (rc={lean_rc})")
        except subprocess.TimeoutExpired:
            return json.dumps({
                "status": "timeout",
                "where": "lean_run",
                "seed": seed,
                "message": f"Lean harness exceeded {LEAN_RUN_TIMEOUT_S}s; optimize harness/parsing and avoid slow per-line IO.",
            })
        except Exception as e:
            return json.dumps({"status": "error", "where": "lean_run", "seed": seed, "message": str(e)})

        if lean_rc != 0:
            return json.dumps({
                "status": "error",
                "where": "lean_run",
                "seed": seed,
                "message": f"Lean harness exited {lean_rc}",
                "stderr": trunc(lean_err, 2500),
                "stdout": trunc(lean_out, 2500),
            })

        # Save trace for inspection
        match = (c_out == lean_out)
        _save_trace(ctx["name"], seed, inputs, c_out, lean_out, match)
        
        # Check that harness actually produced SOME output (not completely empty)
        c_output_lines = [l.strip() for l in c_out.strip().split('\n') if l.strip()]
        num_outputs = len(c_output_lines)
        
        if num_outputs == 0:
            return json.dumps({
                "status": "no_output",
                "where": "output_coverage",
                "seed": seed,
                "input_lines": num_cases,
                "message": "C harness produced no output at all. Tests must produce output to verify behavior.",
            })
        
        if match:
            passed += 1
            runs.append({"seed": seed, "cases": num_cases, "outputs": num_outputs, "status": "pass"})
            continue

        return json.dumps({
            "status": "diff",
            "where": "compare",
            "seed": seed,
            "cases": num_cases,
            "message": "Outputs differ; fix Lean semantics or harness to match C.",
            "c_out": trunc(c_out, 2500),
            "lean_out": trunc(lean_out, 2500),
        })

    total_s = time.time() - t0
    return json.dumps({
        "status": "success",
        "passed_runs": passed,
        "required_runs": DIFF_REQUIRED_RUNS,
        "min_cases_per_run": DIFF_MIN_CASES_PER_RUN,
        "runs": runs,
        "total_time_s": round(total_s, 3),
    })
