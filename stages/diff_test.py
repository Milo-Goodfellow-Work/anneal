"""Differential testing - compare C and Lean harness outputs."""
from __future__ import annotations
import sys, json, time, subprocess, shutil
from pathlib import Path
from typing import Dict, Any, List
from helpers import (log, run_lake_build, run_lake_build_target, list_project_files, 
                     SPEC_DIR, SPEC_SRC_DIR, SPEC_TESTS_DIR,
                     DIFF_REQUIRED_RUNS, DIFF_MIN_CASES_PER_RUN, DIFF_SEED_START,
                     GEN_TIMEOUT_S, C_RUN_TIMEOUT_S, LEAN_RUN_TIMEOUT_S)

GENERATED_DIR = Path("generated")

def _safe_relpath(p: str) -> str:
    return (p or "").replace("\\", "/").lstrip("/").lstrip("./").replace("spec/Src/", "").replace("Src/", "")

def _trunc(s: str, n: int = 2000) -> str:
    return s[:n] + "..." if len(s) > n else s

def run_differential_test_impl(ctx: dict, args: Dict[str, Any]) -> str:
    gen_script = _safe_relpath(args.get("gen_script_path", "spec/tests/gen_inputs.py"))
    c_harness = _safe_relpath(args.get("c_harness_path", "spec/tests/harness.c"))
    lean_harness = _safe_relpath(args.get("lean_harness_path", "tests/Harness.lean"))
    t0 = time.time()

    lean_path = SPEC_SRC_DIR / lean_harness
    if not lean_path.exists():
        lean_path = SPEC_SRC_DIR / "tests/Harness.lean"
    if not lean_path.exists():
        return json.dumps({"status": "error", "message": f"Lean harness not found: {lean_harness}"})

    # Compile C
    exe = SPEC_TESTS_DIR / "harness.exe"
    build_dir = SPEC_TESTS_DIR / "build"
    if build_dir.exists():
        shutil.rmtree(build_dir)
    build_dir.mkdir(parents=True, exist_ok=True)

    proj_srcs = [GENERATED_DIR / f for f in list_project_files(GENERATED_DIR) 
                 if f.endswith(".c") and "main.c" not in f.lower()]
    inc_dirs = {str(GENERATED_DIR.resolve())}
    inc_flags = [f for d in inc_dirs for f in ["-I", d]]
    CFLAGS = ["-std=c11", "-O2"]

    # Compile harness
    harness_o = build_dir / "harness.o"
    cmd = ["gcc", *CFLAGS, *inc_flags, "-c", str(Path(c_harness)), "-o", str(harness_o)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        return json.dumps({"status": "error", "where": "c_harness_compile", "message": _trunc(r.stderr)})

    # Compile project sources
    obj_files = [str(harness_o)]
    for src in proj_srcs:
        o = build_dir / (src.stem + ".o")
        r = subprocess.run(["gcc", *CFLAGS, *inc_flags, "-c", str(src), "-o", str(o)], capture_output=True, text=True)
        if r.returncode != 0:
            return json.dumps({"status": "error", "where": "c_compile", "file": src.name, "message": _trunc(r.stderr)})
        obj_files.append(str(o))

    # Link
    r = subprocess.run(["gcc", *obj_files, "-o", str(exe), "-lm"], capture_output=True, text=True)
    if r.returncode != 0:
        return json.dumps({"status": "error", "where": "c_link", "message": _trunc(r.stderr)})

    # Build Lean
    log("  [DiffTest] lake build...")
    b = run_lake_build(SPEC_DIR)
    if not b.startswith("Build Success"):
        return json.dumps({"status": "error", "where": "lean_build", "message": _trunc(b)})
    log("  [DiffTest] building Harness target...")
    hb = run_lake_build_target(SPEC_DIR, target="Src.tests.Harness")
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
                                     cwd=str(SPEC_DIR), input=inputs,
                                     capture_output=True, text=True, timeout=LEAN_RUN_TIMEOUT_S)
        except subprocess.TimeoutExpired:
            return json.dumps({"status": "timeout", "where": "lean_run", "seed": seed})
        if lean_run.returncode != 0:
            return json.dumps({"status": "error", "where": "lean_run", "seed": seed, "message": _trunc(lean_run.stderr)})

        if c_run.stdout != lean_run.stdout:
            return json.dumps({"status": "diff", "seed": seed, "c_out": _trunc(c_run.stdout), "lean_out": _trunc(lean_run.stdout)})

        passed += 1
        runs.append({"seed": seed, "cases": len(lines), "status": "pass"})

    ctx["equiv_state"]["last_status"] = "success"
    ctx["equiv_state"]["passed_runs"] = passed
    
    return json.dumps({"status": "success", "passed_runs": passed, "required_runs": DIFF_REQUIRED_RUNS,
                       "runs": runs, "total_time_s": round(time.time() - t0, 3)})
