"""Differential testing - compare C and Lean harness outputs."""
from __future__ import annotations
import sys, json, time, subprocess, shutil
from pathlib import Path
from typing import Dict, Any, List
from helpers import (log, run_lake_build, run_lake_build_target, list_project_files, 
                     SPEC_DIR, SPEC_SRC_DIR, SPEC_TESTS_DIR,
                     DIFF_TOTAL_CASES, DIFF_SEED_START,
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

    # -------------------------------------------------------------------------
    # 1. PREPARATION: Compile both the C implementation and the Lean model
    # -------------------------------------------------------------------------
    # We treat both as "black boxes" that must behave identically.
    
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
    # This prepares the specific test harness target in the Lake project.
    log("  [DiffTest] lake build...")
    b = run_lake_build(SPEC_DIR)
    if not b.startswith("Build Success"):
        return json.dumps({"status": "error", "where": "lean_build", "message": _trunc(b)})
    log("  [DiffTest] building Harness target...")
    hb = run_lake_build_target(SPEC_DIR, target="Src.tests.Harness")
    if not hb.startswith("Build Success"):
        return json.dumps({"status": "error", "where": "harness_build", "message": _trunc(hb, 3000)})

    # Run tests - one case at a time
    t0 = time.time()
    all_cases = []
    
    for case_idx in range(DIFF_TOTAL_CASES):
        seed = DIFF_SEED_START + case_idx
        
        # ---------------------------------------------------------------------
        # 2. THE LOOP: Fuzzing
        # ---------------------------------------------------------------------
        # For each test case, we generate specific random inputs.
        
        # Generate one case
        # Calls python gen_inputs.py --seed <N> to get a deterministic random input (e.g. "ALLOC 10; FREE;")
        try:
            gen = subprocess.run([sys.executable, gen_script, "--seed", str(seed)],
                                capture_output=True, text=True, timeout=GEN_TIMEOUT_S)
        except subprocess.TimeoutExpired:
            return json.dumps({"status": "timeout", "where": "generator", "case": case_idx})
        if gen.returncode != 0:
            return json.dumps({"status": "error", "where": "generator", "case": case_idx, "message": _trunc(gen.stderr)})
        
        case_input = gen.stdout
        
        # ---------------------------------------------------------------------
        # 3. EXECUTION: Run both "boxes"
        # ---------------------------------------------------------------------
        
        # Run C harness
        # We feed the generated input into the compiled C executable and capture stdout.
        try:
            c_run = subprocess.run([str(exe)], input=case_input, capture_output=True, text=True, timeout=C_RUN_TIMEOUT_S)
        except subprocess.TimeoutExpired:
            return json.dumps({"status": "timeout", "where": "c_run", "case": case_idx})
        if c_run.returncode != 0:
            return json.dumps({"status": "error", "where": "c_run", "case": case_idx, "message": _trunc(c_run.stderr)})
        
        # Run Lean harness
        # We feed the SAME generated input into the Lean model and capture stdout.
        try:
            lean_run = subprocess.run(["lake", "env", "lean", "--run", str(lean_path)],
                                     cwd=str(SPEC_DIR), input=case_input,
                                     capture_output=True, text=True, timeout=LEAN_RUN_TIMEOUT_S)
        except subprocess.TimeoutExpired:
            return json.dumps({"status": "timeout", "where": "lean_run", "case": case_idx})
        if lean_run.returncode != 0:
            return json.dumps({"status": "error", "where": "lean_run", "case": case_idx, "message": _trunc(lean_run.stderr)})
        
        c_out = c_run.stdout.strip()
        lean_out = lean_run.stdout.strip()
        
        # ---------------------------------------------------------------------
        # 4. VERIFICATION: Compare the witnesses
        # ---------------------------------------------------------------------
        
        if c_out != lean_out:
            return json.dumps({"status": "diff", "case": case_idx, 
                               "input": _trunc(case_input), "c_out": c_out, "lean_out": lean_out})
        
        all_cases.append({"seed": seed, "input": case_input.strip(), "c": c_out, "lean": lean_out, "match": True})

    ctx["equiv_state"]["last_status"] = "success"
    ctx["equiv_state"]["test_data"] = {
        "cases": all_cases,
        "total_cases": len(all_cases),
        "all_pass": True,
    }
    
    return json.dumps({"status": "success", "total_cases": DIFF_TOTAL_CASES,
                       "total_time_s": round(time.time() - t0, 3)})
