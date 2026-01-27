#!/usr/bin/env python3
"""Anneal - Universal Verification Agent. Generates verified C code from prompts."""
import argparse, os, sys, time, shutil
from pathlib import Path

# Copy templates to working directories at startup
TEMPLATE_DIR = Path(__file__).parent / "template"
for name in ["spec", "generated"]:
    if (TEMPLATE_DIR / name).exists():
        shutil.rmtree(name, ignore_errors=True)
        shutil.copytree(TEMPLATE_DIR / name, name)

from google import genai
from helpers import log, load_secrets, SPEC_DIR, SPEC_SRC_DIR, SPEC_TESTS_DIR, DIFF_REQUIRED_RUNS, DIFF_MIN_CASES_PER_RUN
from stages.scaffold import init_project
from stages.cogeneration import run_stage_cogeneration
from stages.proving import run_stage_proving

GCP_JOB_ID = os.environ.get("JOB_ID", "")
GCP_RESULTS_BUCKET = os.environ.get("RESULTS_BUCKET", "")

def is_gcp_mode() -> bool:
    return bool(GCP_JOB_ID and GCP_RESULTS_BUCKET)

def parse_args():
    p = argparse.ArgumentParser(description="Anneal - Generate verified code from prompts")
    p.add_argument("--prompt", "-p", help="Natural language description")
    p.add_argument("--prove-only", action="store_true", help="Skip Stage 1, run only Stage 2")
    return p.parse_args()

def create_context(client, secrets, prompt: str) -> dict:
    return {
        "prompt": prompt,
        "source_root": Path("generated"),
        "spec_pkg_root": SPEC_DIR,
        "spec_src_root": SPEC_SRC_DIR,
        "client": client,
        "secrets": secrets,
        "allowed_lean_writes": set(),
        "allowed_text_writes": set(),
        "locked_lean_paths": set(),
        "current_stage": "INIT",
        "equiv_state": {"last_report": None, "passed_runs": 0, "required_runs": DIFF_REQUIRED_RUNS,
                       "min_cases_per_run": DIFF_MIN_CASES_PER_RUN, "last_status": "unknown"},
    }

def run_generation(prompt: str, prove_only: bool, client, secrets) -> bool:
    ctx = create_context(client, secrets, prompt)
    init_project(ctx)
    if not prove_only:
        run_stage_cogeneration(ctx)
    else:
        ctx["equiv_state"]["last_status"] = "success"
        ctx["equiv_state"]["passed_runs"] = 5
    run_stage_proving(ctx)
    return True

def main() -> None:
    args = parse_args()
    start_time = time.time()
    success, error_msg, callback_url = False, None, None
    
    try:
        if is_gcp_mode():
            from stages.gcp import fetch_job_params, update_job_status
            job = fetch_job_params(GCP_JOB_ID, GCP_RESULTS_BUCKET)
            prompt, callback_url = job["prompt"], job.get("callback_url", "")
            update_job_status(GCP_JOB_ID, GCP_RESULTS_BUCKET, "running")
        else:
            prompt = args.prompt
        
        secrets = load_secrets()
        client = genai.Client(api_key=secrets["secrets"]["GEMINI_API_KEY"])
        
        if prompt or args.prove_only:
            success = run_generation(prompt, args.prove_only, client, secrets)
        else:
            print("Usage: python main.py --prompt 'Create a memory arena'")
            sys.exit(0)
    except Exception as e:
        log(f"ERROR: {e}")
        import traceback; traceback.print_exc()
        error_msg = str(e)
    finally:
        duration = time.time() - start_time
        if is_gcp_mode():
            from stages.gcp import update_job_status, finalize_gcp_job
            update_job_status(GCP_JOB_ID, GCP_RESULTS_BUCKET, "completed" if success else "failed", error_msg, duration)
            finalize_gcp_job(GCP_JOB_ID, success, duration, GCP_RESULTS_BUCKET, callback_url)
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
