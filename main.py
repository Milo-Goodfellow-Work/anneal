#!/usr/bin/env python3
"""Anneal - Universal Verification Agent. Generates verified C code from prompts."""
import argparse, os, shutil, traceback, tomllib
from pathlib import Path

# Copy templates to working directories at startup
TEMPLATE_DIR = Path(__file__).parent / "template"
for name in ["spec", "generated"]:
    if (TEMPLATE_DIR / name).exists():
        shutil.rmtree(name, ignore_errors=True)
        shutil.copytree(TEMPLATE_DIR / name, name)

from google import genai
from helpers import log, SECRETS_FILE, DIFF_REQUIRED_RUNS, DIFF_MIN_CASES_PER_RUN
from stages.cogeneration import run_stage_cogeneration
from stages.proving import run_stage_proving
from stages.gcp import fetch_job_params, update_job_status, finalize_gcp_job

# GCP mode: set by Cloud Run Jobs via env vars
GCP_JOB_ID = os.environ.get("JOB_ID", "")
GCP_RESULTS_BUCKET = os.environ.get("RESULTS_BUCKET", "")
GCP_MODE = bool(GCP_JOB_ID and GCP_RESULTS_BUCKET)

def parse_args():
    p = argparse.ArgumentParser(description="Anneal - Generate verified code from prompts")
    p.add_argument("--prompt", "-p", help="Natural language description")
    p.add_argument("--prove-only", action="store_true", help="Skip Stage 1, run only Stage 2")
    return p.parse_args()

def create_context(client, secrets, prompt: str) -> dict:
    return {
        "prompt": prompt,
        "client": client,
        "secrets": secrets,
        "equiv_state": {"last_report": None, "passed_runs": 0, "required_runs": DIFF_REQUIRED_RUNS,
                       "min_cases_per_run": DIFF_MIN_CASES_PER_RUN, "last_status": "unknown"},
    }

def run_generation(prompt: str, prove_only: bool, client, secrets) -> None:
    ctx = create_context(client, secrets, prompt)
    if not prove_only:
        run_stage_cogeneration(ctx)
    else:
        ctx["equiv_state"]["last_status"] = "success"
        ctx["equiv_state"]["passed_runs"] = 5
    run_stage_proving(ctx)

def main() -> None:
    prove_only, success, error_msg = False, True, None
    
    # GCP mode: secrets from env vars, prompt from GCS job params
    if GCP_MODE:
        gemini_key = os.environ.get("GEMINI_API_KEY")
        if not gemini_key:
            raise EnvironmentError("GEMINI_API_KEY not set in environment")
        secrets = {"secrets": {"GEMINI_API_KEY": gemini_key, "ARISTOTLE_API_KEY": os.environ.get("ARISTOTLE_API_KEY", "")}}
        
        job = fetch_job_params(GCP_JOB_ID, GCP_RESULTS_BUCKET)
        prompt = job["prompt"]
        callback_url = job.get("callback_url", "")
        update_job_status(GCP_JOB_ID, GCP_RESULTS_BUCKET, "running")
    # Local mode: secrets from secrets.toml, prompt from CLI
    else:
        args = parse_args()
        if not SECRETS_FILE.exists():
            raise FileNotFoundError(f"{SECRETS_FILE} not found")
        with SECRETS_FILE.open("rb") as f:
            secrets = tomllib.load(f)
        
        prompt = args.prompt
        callback_url = None
        prove_only = args.prove_only
        if not prompt and not prove_only:
            print("Usage: python main.py --prompt 'Create a memory arena'")
            return
    
    client = genai.Client(api_key=secrets["secrets"]["GEMINI_API_KEY"])
    
    try:
        run_generation(prompt, prove_only, client, secrets)
    except Exception as e:
        log(f"ERROR: {e}")
        traceback.print_exc()
        success, error_msg = False, str(e)
    
    if GCP_MODE:
        update_job_status(GCP_JOB_ID, GCP_RESULTS_BUCKET, "completed" if success else "failed", error_msg)
        finalize_gcp_job(GCP_JOB_ID, success, GCP_RESULTS_BUCKET, callback_url)

if __name__ == "__main__":
    main()
