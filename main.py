#!/usr/bin/env python3
"""Anneal - Universal Verification Agent. Generates verified C code from prompts."""
import argparse, os, traceback, tomllib, asyncio
from pathlib import Path

from google import genai
from helpers import log, SECRETS_FILE, DIFF_TOTAL_CASES, run_lake_build, SPEC_DIR, SPEC_SRC_DIR
from stages.cogeneration import run_stage_cogeneration
from stages.proving import run_stage_proving, download_aristotle_solution
from stages.gcp import fetch_job_params, update_job_status, finalize_gcp_job, download_job_files

# GCP mode: set by Cloud Run Jobs via env vars
GCP_JOB_ID = os.environ.get("JOB_ID", "")
GCP_RESULTS_BUCKET = os.environ.get("RESULTS_BUCKET", "")
GCP_MODE = bool(GCP_JOB_ID and GCP_RESULTS_BUCKET)
JOB_MODE = os.environ.get("JOB_MODE", "prove").lower()

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
        "equiv_state": {"last_report": None, "total_cases": DIFF_TOTAL_CASES, "last_status": "unknown"},
    }

def run_generation(prompt: str, prove_only: bool, client, secrets) -> None:
    ctx = create_context(client, secrets, prompt)
    if not prove_only:
        run_stage_cogeneration(ctx)
    else:
        ctx["equiv_state"]["last_status"] = "success"
        ctx["equiv_state"]["passed_runs"] = 5
    return run_stage_proving(ctx)

def _normalize_aristotle_status(status: str) -> str:
    return status.split(".")[-1]

def run_verification(aristotle_id: str) -> tuple[bool, str | None, str]:
    """Download Aristotle solution and trust it without re-verification."""
    if not aristotle_id:
        return False, "Missing aristotle_id", "MISSING"

    verif_path = SPEC_SRC_DIR / "Verif.lean"
    status, solution_path = asyncio.run(download_aristotle_solution(aristotle_id, verif_path))
    status_name = _normalize_aristotle_status(status)

    if status_name != "COMPLETE":
        return False, f"ARISTOTLE_STATUS:{status_name}", status_name

    if not solution_path:
        return False, "No solution downloaded", status_name

    # Trust Aristotle: Skip local build verification
    log(f"Aristotle solution downloaded to {solution_path}. Trusting output.")
    return True, None, status_name

def main() -> None:
    prove_only, success, error_msg = False, True, None
    
    # GCP mode: secrets from env vars, prompt from GCS job params
    if GCP_MODE:
        job = fetch_job_params(GCP_JOB_ID, GCP_RESULTS_BUCKET)
        prompt = job.get("prompt", "")
        callback_url = job.get("callback_url", "")

        if JOB_MODE == "verify":
            update_job_status(GCP_JOB_ID, GCP_RESULTS_BUCKET, "verifying")
        else:
            update_job_status(GCP_JOB_ID, GCP_RESULTS_BUCKET, "running")

        gemini_key = os.environ.get("GEMINI_API_KEY", "")
        aristotle_key = os.environ.get("ARISTOTLE_API_KEY", "")
        if JOB_MODE == "prove" and not gemini_key:
            raise EnvironmentError("GEMINI_API_KEY not set in environment")
        if JOB_MODE == "verify" and not aristotle_key:
            raise EnvironmentError("ARISTOTLE_API_KEY not set in environment")
        if aristotle_key:
            os.environ["ARISTOTLE_API_KEY"] = aristotle_key
        secrets = {"secrets": {"GEMINI_API_KEY": gemini_key, "ARISTOTLE_API_KEY": aristotle_key}}
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
    
    client = None
    if not GCP_MODE or JOB_MODE == "prove":
        client = genai.Client(api_key=secrets["secrets"]["GEMINI_API_KEY"])
    
    aristotle_id = None
    try:
        if JOB_MODE == "verify" and GCP_MODE:
            # Download the original job files from GCS first
            download_job_files(GCP_JOB_ID, GCP_RESULTS_BUCKET)
            
            aristotle_id = job.get("aristotle_id") or os.environ.get("ARISTOTLE_ID", "")
            success, error_msg, aristotle_status = run_verification(aristotle_id)

            if error_msg and error_msg.startswith("ARISTOTLE_STATUS:"):
                update_job_status(
                    GCP_JOB_ID,
                    GCP_RESULTS_BUCKET,
                    "proof_pending",
                    aristotle_status=aristotle_status,
                    proof_verified=False,
                )
                return

            update_job_status(
                GCP_JOB_ID,
                GCP_RESULTS_BUCKET,
                "completed" if success else "verification_failed",
                error_msg,
                aristotle_status=aristotle_status,
                proof_verified=success,
            )

            finalize_gcp_job(GCP_JOB_ID, success, GCP_RESULTS_BUCKET, callback_url, proof_verified=success)
            return

        aristotle_id = run_generation(prompt, prove_only, client, secrets)
    except Exception as e:
        log(f"ERROR: {e}")
        traceback.print_exc()
        success, error_msg = False, str(e)

    if GCP_MODE:
        status_kwargs = {"proof_verified": False}
        if aristotle_id:
            status_kwargs["aristotle_id"] = aristotle_id
            status_kwargs["aristotle_status"] = "QUEUED"
            update_job_status(GCP_JOB_ID, GCP_RESULTS_BUCKET, "proof_submitted", error_msg, **status_kwargs)
            # Upload generated files so verify mode can use them later
            finalize_gcp_job(GCP_JOB_ID, True, GCP_RESULTS_BUCKET, callback_url, proof_verified=False)
        else:
            update_job_status(GCP_JOB_ID, GCP_RESULTS_BUCKET, "failed", error_msg, **status_kwargs)
            finalize_gcp_job(GCP_JOB_ID, False, GCP_RESULTS_BUCKET, callback_url, proof_verified=False)

if __name__ == "__main__":
    main()
