#!/usr/bin/env python3
"""GCP Integration - Job storage and results upload."""
import json
import os
from pathlib import Path
from datetime import datetime
from typing import Optional
from helpers import log

def fetch_job_params(job_id: str, bucket: str) -> dict:
    """Fetch job params from gs://bucket/jobs/{job_id}.json"""
    from google.cloud import storage
    project_id = os.environ.get("PROJECT_ID")
    blob = storage.Client(project=project_id).bucket(bucket).blob(f"jobs/{job_id}.json")
    params = json.loads(blob.download_as_text())
    if "prompt" not in params:
        raise ValueError(f"Job {job_id} missing prompt")
    return params

def update_job_status(job_id: str, bucket: str, status: str, error: Optional[str] = None, **kwargs) -> dict:
    """Update job status in GCS."""
    from google.cloud import storage
    project_id = os.environ.get("PROJECT_ID")
    blob = storage.Client(project=project_id).bucket(bucket).blob(f"jobs/{job_id}.json")
    params = json.loads(blob.download_as_text())
    params["status"] = status
    params["updated_at"] = datetime.now().isoformat()
    if status == "running":
        params["started_at"] = datetime.now().isoformat()
    elif status in ("completed", "failed"):
        params["finished_at"] = datetime.now().isoformat()
        if error: params["error"] = error
    params.update(kwargs)
    blob.upload_from_string(json.dumps(params, indent=2))
    return params

def _collect_files() -> list[Path]:
    files = []
    for d in [Path("generated"), Path("spec/Src")]:
        if d.exists():
            files.extend(f for f in d.rglob("*") if f.is_file())
    reports = Path("spec/reports")
    if reports.exists():
        files.extend(f for f in reports.glob("*") if f.is_file())
    return files

def upload_results(job_id: str, bucket: str, success: bool) -> dict:
    """Upload results to GCS."""
    from google.cloud import storage
    project_id = os.environ.get("PROJECT_ID")
    bkt = storage.Client(project=project_id).bucket(bucket)
    files = _collect_files()

    # Generate a unique run ID (timestamp)
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    log(f"Uploading {len(files)} files to:")
    log(f"  - gs://{bucket}/{job_id}/{run_id}/ (History)")
    log(f"  - gs://{bucket}/{job_id}/latest/ (Current)")

    for f in files:
        # Upload to history path
        bkt.blob(f"{job_id}/{run_id}/{f}").upload_from_filename(str(f))
        # Upload to latest path (overwrite)
        bkt.blob(f"{job_id}/latest/{f}").upload_from_filename(str(f))

    status = {
        "job_id": job_id,
        "status": "completed" if success else "failed",
        "latest_run_id": run_id,
        "files_uploaded": len(files),
        "completed_at": datetime.now().isoformat(),
        "history_path": f"gs://{bucket}/{job_id}/{run_id}/",
        "latest_path": f"gs://{bucket}/{job_id}/latest/"
    }
    
    # Update the run-specific status file
    bkt.blob(f"{job_id}/{run_id}/status.json").upload_from_string(json.dumps(status, indent=2))
    # Update the latest status file
    bkt.blob(f"{job_id}/latest/status.json").upload_from_string(json.dumps(status, indent=2))
    
    log(f"Upload complete. Status: {status['status']}")
    return status

def call_webhook(url: str, job_id: str, status: dict, bucket: Optional[str] = None):
    if not url: return
    import urllib.request, urllib.error
    payload = json.dumps({"job_id": job_id, "status": status["status"], 
                          "results_url": f"gs://{bucket}/{job_id}/" if bucket else None}).encode()
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
    try:
        urllib.request.urlopen(req, timeout=30)
    except urllib.error.URLError:
        pass

def finalize_gcp_job(job_id: str, success: bool, bucket: Optional[str] = None, callback_url: Optional[str] = None):
    if not bucket: return
    status = upload_results(job_id, bucket, success)
    if callback_url:
        call_webhook(callback_url, job_id, status, bucket)
    return status
