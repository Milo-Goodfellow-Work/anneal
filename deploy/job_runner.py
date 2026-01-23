#!/usr/bin/env python3
"""
Anneal GCP Job Runner

Consumes jobs from environment variables (set by Cloud Run),
runs Anneal, uploads results to GCS, and calls webhook.
"""
import os
import sys
import json
import subprocess
from pathlib import Path
from datetime import datetime
from google.cloud import storage

# Job parameters from environment
JOB_ID = os.environ.get("JOB_ID", "local-test")
PROMPT = os.environ.get("PROMPT", "")
PROJECT_NAME = os.environ.get("PROJECT_NAME", "generated")
CALLBACK_URL = os.environ.get("CALLBACK_URL", "")
RESULTS_BUCKET = os.environ.get("RESULTS_BUCKET", "anneal-results")

# Secrets from Secret Manager (injected by Cloud Run)
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
ARISTOTLE_API_KEY = os.environ.get("ARISTOTLE_API_KEY", "")


def log(msg: str):
    """Log with timestamp."""
    print(f"[{datetime.now().isoformat()}] {msg}", flush=True)


def write_secrets():
    """Write secrets to secrets.toml for Anneal to read."""
    secrets_content = f'''[secrets]
GEMINI_API_KEY = "{GEMINI_API_KEY}"
ARISTOTLE_API_KEY = "{ARISTOTLE_API_KEY}"
'''
    Path("secrets.toml").write_text(secrets_content)
    log("Wrote secrets.toml")


def run_anneal() -> dict:
    """Run Anneal with the job parameters."""
    log(f"Starting Anneal job: {JOB_ID}")
    log(f"Project: {PROJECT_NAME}")
    log(f"Prompt: {PROMPT[:100]}...")
    
    cmd = [
        "python", "main.py",
        "--prompt", PROMPT,
        "--project", PROJECT_NAME,
    ]
    
    start_time = datetime.now()
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=3600,  # 60 minute timeout
    )
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    
    log(f"Anneal completed in {duration:.1f}s with exit code {result.returncode}")
    
    return {
        "exit_code": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "duration_seconds": duration,
    }


def upload_results(anneal_result: dict):
    """Upload generated files to GCS."""
    log(f"Uploading results to gs://{RESULTS_BUCKET}/{JOB_ID}/")
    
    client = storage.Client()
    bucket = client.bucket(RESULTS_BUCKET)
    
    # Collect files to upload
    files_to_upload = []
    
    # Generated implementation
    gen_dir = Path(f"generated/{PROJECT_NAME}")
    if gen_dir.exists():
        for f in gen_dir.rglob("*"):
            if f.is_file():
                files_to_upload.append(f)
    
    # Lean specs
    spec_dir = Path(f"spec/Spec/{PROJECT_NAME}")
    if spec_dir.exists():
        for f in spec_dir.rglob("*"):
            if f.is_file():
                files_to_upload.append(f)
    
    # Reports
    reports_dir = Path("spec/reports")
    if reports_dir.exists():
        for f in reports_dir.glob(f"{PROJECT_NAME}*"):
            if f.is_file():
                files_to_upload.append(f)
    
    # Upload each file
    for local_path in files_to_upload:
        # Compute GCS path
        rel_path = str(local_path)
        gcs_path = f"{JOB_ID}/{rel_path}"
        
        blob = bucket.blob(gcs_path)
        blob.upload_from_filename(str(local_path))
        log(f"  Uploaded: {rel_path}")
    
    # Upload status.json
    status = {
        "job_id": JOB_ID,
        "project_name": PROJECT_NAME,
        "status": "completed" if anneal_result["exit_code"] == 0 else "failed",
        "exit_code": anneal_result["exit_code"],
        "duration_seconds": anneal_result["duration_seconds"],
        "files_uploaded": len(files_to_upload),
        "completed_at": datetime.now().isoformat(),
    }
    
    status_blob = bucket.blob(f"{JOB_ID}/status.json")
    status_blob.upload_from_string(json.dumps(status, indent=2))
    log("Uploaded status.json")
    
    return status


def call_webhook(status: dict):
    """Call the callback URL to notify completion."""
    if not CALLBACK_URL:
        log("No callback URL configured, skipping webhook")
        return
    
    import urllib.request
    import urllib.error
    
    payload = json.dumps({
        "job_id": JOB_ID,
        "status": status["status"],
        "results_url": f"gs://{RESULTS_BUCKET}/{JOB_ID}/",
        "duration_seconds": status["duration_seconds"],
    }).encode()
    
    req = urllib.request.Request(
        CALLBACK_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            log(f"Webhook called successfully: {resp.status}")
    except urllib.error.URLError as e:
        log(f"Webhook failed: {e}")


def main():
    """Main job runner entry point."""
    log("=" * 60)
    log("Anneal GCP Job Runner Starting")
    log("=" * 60)
    
    if not PROMPT:
        log("ERROR: No PROMPT environment variable set")
        sys.exit(1)
    
    if not GEMINI_API_KEY:
        log("ERROR: No GEMINI_API_KEY environment variable set")
        sys.exit(1)
    
    try:
        # Write secrets file
        write_secrets()
        
        # Run Anneal
        anneal_result = run_anneal()
        
        # Upload results
        status = upload_results(anneal_result)
        
        # Call webhook
        call_webhook(status)
        
        log("=" * 60)
        log(f"Job {JOB_ID} completed with status: {status['status']}")
        log("=" * 60)
        
        # Exit with Anneal's exit code
        sys.exit(anneal_result["exit_code"])
        
    except Exception as e:
        log(f"FATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
