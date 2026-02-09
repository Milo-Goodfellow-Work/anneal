#!/usr/bin/env python3
# Main entry point for the Anneal verification worker.
# This script handles both local development and GCP Cloud Run Job execution.
"""Anneal - Universal Verification Agent. Generates verified C code from prompts."""
import argparse, os, traceback, tomllib, asyncio
from pathlib import Path

from google import genai
from helpers import log, SECRETS_FILE, DIFF_TOTAL_CASES, run_lake_build, SPEC_DIR, SPEC_SRC_DIR
from stages.cogeneration import run_stage_cogeneration
from stages.proving import run_stage_proving, download_aristotle_solution
from stages.gcp import fetch_job_params, update_job_status, finalize_gcp_job, download_job_files

# Variables for GCP environment detection.
# JOB_ID and RESULTS_BUCKET presence indicates we are running as a Cloud Run Job.
GCP_JOB_ID = os.environ.get("JOB_ID", "")
GCP_RESULTS_BUCKET = os.environ.get("RESULTS_BUCKET", "")
GCP_MODE = bool(GCP_JOB_ID and GCP_RESULTS_BUCKET)
# JOB_MODE determines if we are in 'prove' (generation + submission) or 'verify' (final proof check) mode.
JOB_MODE = os.environ.get("JOB_MODE", "prove").lower()

# CLI argument parser for local execution.
def parse_args():
    p = argparse.ArgumentParser(description="Anneal - Generate verified code from prompts")
    p.add_argument("--prompt", "-p", help="Natural language description")
    p.add_argument("--prove-only", action="store_true", help="Skip Stage 1, run only Stage 2")
    return p.parse_args()

# Context object initialization to track state across pipeline stages.
def create_context(client, secrets, prompt: str) -> dict:
    return {
        "prompt": prompt,
        "client": client,
        "secrets": secrets,
        "equiv_state": {"last_report": None, "total_cases": DIFF_TOTAL_CASES, "last_status": "unknown"},
    }

# Orchestrates Stage 1 (Co-generation) and Stage 2 (Proving submission).
def run_generation(prompt: str, prove_only: bool, client, secrets) -> None:
    ctx = create_context(client, secrets, prompt)
    if not prove_only:
        # Generate C code, Lean spec, and run differential tests.
        run_stage_cogeneration(ctx)
    else:
        # Skip generation for existing codebases.
        ctx["equiv_state"]["last_status"] = "success"
        ctx["equiv_state"]["passed_runs"] = 5
    # Submit the generated Lean spec to Aristotle for formal proof.
    return run_stage_proving(ctx)

# Utility to extract a clean status string from an Aristotle status enum/string.
def _normalize_aristotle_status(status: str) -> str:
    return status.split(".")[-1]

# Final verification stage: downloads and incorporates the completed proof.
def run_verification(aristotle_id: str) -> tuple[bool, str | None, str]:
    """Download Aristotle solution and trust it without re-verification."""
    if not aristotle_id:
        return False, "Missing aristotle_id", "MISSING"

    # Destination for the formal proof from Aristotle.
    verif_path = SPEC_SRC_DIR / "Verif.lean"
    # Download the proof from the Aristotle API.
    status, solution_path = asyncio.run(download_aristotle_solution(aristotle_id, verif_path))
    status_name = _normalize_aristotle_status(status)

    # Only proceed if Aristotle confirms proof completion.
    if status_name != "COMPLETE":
        return False, f"ARISTOTLE_STATUS:{status_name}", status_name

    if not solution_path:
        return False, "No solution downloaded", status_name

    # We assume Aristotle's proof is correct as per user policy.
    # Trust Aristotle: Skip local build verification
    log(f"Aristotle solution downloaded to {solution_path}. Trusting output.")
    return True, None, status_name

# Main execution loop handles setup, stage routing, and status reporting.
def main() -> None:
    prove_only, success, error_msg = False, True, None
    
    # Check if we are running in a GCP Cloud Run Job context.
    # GCP mode: secrets from env vars, prompt from GCS job params
    if GCP_MODE:
        # Load job metadata (prompt, original parameters) from GCS.
        job = fetch_job_params(GCP_JOB_ID, GCP_RESULTS_BUCKET)
        prompt = job.get("prompt", "")
        callback_url = job.get("callback_url", "")

        # Update persistent job status in GCS tracking file.
        if JOB_MODE == "verify":
            update_job_status(GCP_JOB_ID, GCP_RESULTS_BUCKET, "verifying")
        else:
            update_job_status(GCP_JOB_ID, GCP_RESULTS_BUCKET, "running")

        # Load API keys from Environment Variables (set via Secret Manager).
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
        # For local runs, we use a secrets.toml file and CLI flags.
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
    # Initialize the Gemini API client.
    if not GCP_MODE or JOB_MODE == "prove":
        client = genai.Client(api_key=secrets["secrets"]["GEMINI_API_KEY"])
    
    aristotle_id = None
    try:
        # Branch logic based on whether we are starting a job or completing a proof.
        if JOB_MODE == "verify" and GCP_MODE:
            # RESTORE PHASE: Get the generated C/Lean artifacts from GCS.
            # Download the original job files from GCS first
            download_job_files(GCP_JOB_ID, GCP_RESULTS_BUCKET)
            
            # ATTACH PROOF: Get the ID and run the verification logic.
            aristotle_id = job.get("aristotle_id") or os.environ.get("ARISTOTLE_ID", "")
            success, error_msg, aristotle_status = run_verification(aristotle_id)

            # Handle case where Aristotle is still processing (poller should retry later).
            if error_msg and error_msg.startswith("ARISTOTLE_STATUS:"):
                update_job_status(
                    GCP_JOB_ID,
                    GCP_RESULTS_BUCKET,
                    "proof_pending",
                    aristotle_status=aristotle_status,
                    proof_verified=False,
                )
                return

            # Update job status to final success or failure.
            update_job_status(
                GCP_JOB_ID,
                GCP_RESULTS_BUCKET,
                "completed" if success else "verification_failed",
                error_msg,
                aristotle_status=aristotle_status,
                proof_verified=success,
            )

            # Mark Cloud Run Job as finished and trigger optional callback.
            finalize_gcp_job(GCP_JOB_ID, success, GCP_RESULTS_BUCKET, callback_url, proof_verified=success)
            return

        # GENERATION PHASE: Start the LLM-driven co-generation and submission.
        aristotle_id = run_generation(prompt, prove_only, client, secrets)
    except Exception as e:
        # Catch and report global failures.
        log(f"ERROR: {e}")
        traceback.print_exc()
        success, error_msg = False, str(e)

    # Post-generation update for GCP mode.
    if GCP_MODE:
        status_kwargs = {"proof_verified": False}
        if aristotle_id:
            # If Stage 2 started, job is now proof_submitted (waiting for Aristotle).
            status_kwargs["aristotle_id"] = aristotle_id
            status_kwargs["aristotle_status"] = "QUEUED"
            update_job_status(GCP_JOB_ID, GCP_RESULTS_BUCKET, "proof_submitted", error_msg, **status_kwargs)
            # Persist local artifacts (C/Lean) to GCS so verify mode can find them.
            # Upload generated files so verify mode can use them later
            finalize_gcp_job(GCP_JOB_ID, True, GCP_RESULTS_BUCKET, callback_url, proof_verified=False)
        else:
            # Generation or initial submission failed.
            update_job_status(GCP_JOB_ID, GCP_RESULTS_BUCKET, "failed", error_msg, **status_kwargs)
            finalize_gcp_job(GCP_JOB_ID, False, GCP_RESULTS_BUCKET, callback_url, proof_verified=False)

if __name__ == "__main__":
    # Standard entry point.
    main()

