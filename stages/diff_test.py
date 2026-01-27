"""Differential testing - compare C and Lean harness outputs."""
from __future__ import annotations
import sys, json, time, subprocess, shlex
from pathlib import Path
from typing import Dict, Any, List
from helpers import (run_lake_build, run_lake_build_target, list_project_files, SPEC_TESTS_DIR,
                     DIFF_REQUIRED_RUNS, DIFF_MIN_CASES_PER_RUN, DIFF_SEED_START,
                     GEN_TIMEOUT_S, C_RUN_TIMEOUT_S, LEAN_RUN_TIMEOUT_S)

def _safe_relpath(p: str) -> str:
    return (p or "").replace("\\", "/").lstrip("/").lstrip("./").replace("spec/Src/", "").replace("Src/", "")

def _trunc(s: str, n: int = 2000) -> str:
    return s[:n] + "..." if len(s) > n else s

def run_differential_test_impl(ctx: dict, args: Dict[str, Any]) -> str:
    gen_script = _safe_relpath(args.get("gen_script_path", "spec/tests/gen_inputs.py"))
    c_harness = _safe_relpath(args.get("c_harness_path", "spec/tests/harness.c"))
    lean_harness = _safe_relpath(args.get("lean_harness_path", "tests/Harness.lean"))
    t0 = time.time()

    lean_path = ctx["spec_src_root"] / lean_harness
    if not lean_path.exists():
        lean_path = ctx["spec_src_root"] / "tests/Harness.lean"
    if not lean_path.exists():
        return json.dumps({"status": "error", "message": f"Lean harness not found: {lean_harness}"})

    # Compile C
    import shutil
    exe = SPEC_TESTS_DIR / "harness.exe"
    build_dir = SPEC_TESTS_DIR / "build"
    if build_dir.exists():
        shutil.rmtree(build_dir)
    build_dir.mkdir(parents=True, exist_ok=True)

    proj_srcs = [ctx["source_root"] / f for f in list_project_files(ctx["source_root"]) 
                 if f.endswith(".c") and "main.c" not in f.lower()]
    inc_dirs = {str(ctx["source_root"].resolve())}
    inc_flags = [f for d in inc_dirs for f in ["-I", d]]
    CFLAGS = ["-std=c11", "-O2"]

    # Compile harness
    harness_o = build_dir / "harness.o"
    cmd = ["gcc", *CFLAGS, *inc_flags, "-c", str(Path(c_harness)), "-o", str(harness_o)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        return json.dumps({"status": "error", "where": "c_compile", "message": _trunc(r.stderr)})

    # Compile project sources
    objs = [harness_o]
    for src in proj_srcs:
        obj = build_dir / (src.stem + ".o")
        r = subprocess.run(["gcc", *CFLAGS, *inc_flags, "-c", str(src), "-o", str(obj)], capture_output=True, text=True)
        if r.returncode != 0:
            return json.dumps({"status": "error", "where": "c_compile", "message": _trunc(r.stderr)})
        objs.append(obj)

    # Link
    r = subprocess.run(["gcc", "-o", str(exe)] + [str(o) for o in objs], capture_output=True, text=True)
    if r.returncode != 0:
        return json.dumps({"status": "error", "where": "c_link", "message": _trunc(r.stderr)})

    # Build Lean
    from helpers import log
    log("  [DiffTest] lake build...")
    b = run_lake_build(ctx["spec_pkg_root"])
    if not b.startswith("Build Success"):
        return json.dumps({"status": "error", "where": "lean_build", "message": _trunc(b)})
    log("  [DiffTest] building Harness target...")
    hb = run_lake_build_target(ctx["spec_pkg_root"], target="Src.tests.Harness")
    if not hb.startswith("Build Success"):
        return json.dumps({"status": "error", "where": "harness_build", "message": _trunc(hb, 3000)})

    # Run tests
    runs, passed = [], 0
    for k in range(DIFF_REQUIRED_RUNS):
        seed = DIFF_SEED_START + k
        try:
            gen = subprocess.run([sys.executable, gen_script, "--seed", str(seed), "--n", str(DIFF_MIN_CASES_PER_RUN)],
                                capture_output=True, text=True, timeout=GEN_TIMEOUT_S)
        except subprocess.TimeoutExpired:
            return json.dumps({"status": "timeout", "where": "generator", "seed": seed})
        if gen.returncode != 0:
            return json.dumps({"status": "error", "where": "generator", "seed": seed, "message": _trunc(gen.stderr)})
        
        inputs = gen.stdout
        lines = [l for l in inputs.splitlines() if l.strip()]
        if len(lines) < DIFF_MIN_CASES_PER_RUN:
            return json.dumps({"status": "error", "where": "generator", "message": f"Only {len(lines)} cases"})

        # Run C
        try:
            c_run = subprocess.run([str(exe)], input=inputs, capture_output=True, text=True, timeout=C_RUN_TIMEOUT_S)
        except subprocess.TimeoutExpired:
            return json.dumps({"status": "timeout", "where": "c_run", "seed": seed})
        if c_run.returncode != 0:
            return json.dumps({"status": "error", "where": "c_run", "seed": seed, "message": _trunc(c_run.stderr)})

        # Run Lean
        try:
            lean_run = subprocess.run(["lake", "env", "lean", "--run", str(lean_path)],
                                     cwd=str(ctx["spec_pkg_root"]), input=inputs,
                                     capture_output=True, text=True, timeout=LEAN_RUN_TIMEOUT_S)
        except subprocess.TimeoutExpired:
            return json.dumps({"status": "timeout", "where": "lean_run", "seed": seed})
        if lean_run.returncode != 0:
            return json.dumps({"status": "error", "where": "lean_run", "seed": seed, "message": _trunc(lean_run.stderr)})

        if c_run.stdout != lean_run.stdout:
            return json.dumps({"status": "diff", "seed": seed, "c_out": _trunc(c_run.stdout), "lean_out": _trunc(lean_run.stdout)})

        passed += 1
        runs.append({"seed": seed, "cases": len(lines), "status": "pass"})

    return json.dumps({"status": "success", "passed_runs": passed, "required_runs": DIFF_REQUIRED_RUNS,
                       "runs": runs, "total_time_s": round(time.time() - t0, 3)})
