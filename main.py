#!/usr/bin/env python3
"""Anneal - Universal Verification Agent. Generates verified C code from prompts."""
import argparse, os, sys, time, shutil
from pathlib import Path
from google import genai
from helpers import (log, load_secrets, ensure_prelude_and_lockdown, SPEC_DIR, SPEC_SRC_DIR, 
                     SPEC_TESTS_DIR, SPEC_REPORTS_DIR, DIFF_REQUIRED_RUNS, DIFF_MIN_CASES_PER_RUN, LOCKED_LEAN_FILENAMES)
from stages.scaffold import create_project_from_prompt
from stages.cogeneration import run_stage_cogeneration
from stages.proving import run_stage_proving

GCP_JOB_ID = os.environ.get("JOB_ID", "")
GCP_RESULTS_BUCKET = os.environ.get("RESULTS_BUCKET", "")

def is_gcp_mode() -> bool:
    return bool(GCP_JOB_ID and GCP_RESULTS_BUCKET)

def parse_args():
    p = argparse.ArgumentParser(description="Anneal - Generate verified code from prompts")
    p.add_argument("--prompt", "-p", help="Natural language description")
    p.add_argument("--project", "-n", default="generated", help="Project name")
    p.add_argument("--prove-only", action="store_true", help="Skip Stage 1, run only Stage 2")
    p.add_argument("--clear", "-c", action="store_true", help="Clear generated files first")
    return p.parse_args()

def clear_environment(name: str) -> None:
    log(f"Clearing environment for {name}...")
    for d in [Path("generated") / name, SPEC_SRC_DIR / name]:
        if d.exists(): shutil.rmtree(d); log(f"  Removed {d}")
    for f in [SPEC_SRC_DIR / f"{name}.lean"]:
        if f.exists(): f.unlink(); log(f"  Removed {f}")
    if SPEC_TESTS_DIR.exists():
        for f in SPEC_TESTS_DIR.iterdir():
            if f.is_file(): f.unlink()
    # Remove stale import from Spec.lean
    spec_file = SPEC_DIR / "Spec.lean"
    if spec_file.exists():
        import_line = f"import Spec.{name}"
        lines = [l for l in spec_file.read_text().splitlines() if l.strip() != import_line]
        spec_file.write_text("\n".join(lines) + "\n" if lines else "")
        log(f"  Cleaned {spec_file}")

def create_context(client, secrets, name: str, prompt: str) -> dict:
    (SPEC_SRC_DIR / name).mkdir(parents=True, exist_ok=True)
    impl_root = Path("generated") / name
    impl_root.mkdir(parents=True, exist_ok=True)
    return {
        "name": name, "prompt": prompt, "source_root": impl_root,
        "spec_pkg_root": SPEC_DIR, "spec_src_root": SPEC_SRC_DIR,
        "spec_project_root": SPEC_SRC_DIR / name, "client": client, "secrets": secrets,
        "allowed_lean_writes": set(), "allowed_text_writes": set(), "locked_lean_paths": set(LOCKED_LEAN_FILENAMES),
        "src_to_lean": {}, "lean_to_src": {}, "current_stage": "INIT",
        "equiv_state": {"last_report": None, "passed_runs": 0, "required_runs": DIFF_REQUIRED_RUNS,
                       "min_cases_per_run": DIFF_MIN_CASES_PER_RUN, "last_status": "unknown"},
        "equiv_report_rel": f"spec/reports/{name}_equiv.json",
    }

def run_generation(prompt: str, name: str, prove_only: bool, client, secrets) -> bool:
    ctx = create_context(client, secrets, name, prompt)
    create_project_from_prompt(ctx)
    if not prove_only:
        run_stage_cogeneration(ctx)
    else:
        ctx["equiv_state"]["last_status"] = "success"
        ctx["equiv_state"]["passed_runs"] = 5
    run_stage_proving(ctx)
    return True

def main() -> None:
    ensure_prelude_and_lockdown()
    args = parse_args()
    start_time = time.time()
    success, error_msg, project_name, callback_url = False, None, None, None
    
    try:
        if is_gcp_mode():
            from stages.gcp import fetch_job_params, update_job_status
            job = fetch_job_params(GCP_JOB_ID, GCP_RESULTS_BUCKET)
            prompt, project_name, callback_url = job["prompt"], job["project_name"], job.get("callback_url", "")
            update_job_status(GCP_JOB_ID, GCP_RESULTS_BUCKET, "running")
        else:
            prompt, project_name = args.prompt, args.project
        
        if args.clear: clear_environment(project_name)
        secrets = load_secrets()
        client = genai.Client(api_key=secrets["secrets"]["GEMINI_API_KEY"])
        
        if prompt or args.prove_only:
            success = run_generation(prompt, project_name, args.prove_only, client, secrets)
        else:
            print("Usage: python main.py --prompt 'Create a memory arena'")
            sys.exit(0)
    except Exception as e:
        log(f"ERROR: {e}")
        error_msg = str(e)
    finally:
        duration = time.time() - start_time
        if is_gcp_mode():
            from stages.gcp import update_job_status, finalize_gcp_job
            update_job_status(GCP_JOB_ID, GCP_RESULTS_BUCKET, "completed" if success else "failed", error_msg, duration)
            finalize_gcp_job(GCP_JOB_ID, project_name or "x", success, duration, GCP_RESULTS_BUCKET, callback_url)
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
