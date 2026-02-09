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
    if status == "running" or status == "verifying":
        params["started_at"] = datetime.now().isoformat()
    elif status in ("completed", "failed", "verification_failed"):
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

def upload_results(job_id: str, bucket: str, success: bool, proof_verified: bool = False) -> dict:
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
        "proof_verified": proof_verified,
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

def finalize_gcp_job(job_id: str, success: bool, bucket: Optional[str] = None, callback_url: Optional[str] = None, proof_verified: bool = False):
    if not bucket: return None
    status = upload_results(job_id, bucket, success, proof_verified=proof_verified)
    if callback_url:
        call_webhook(callback_url, job_id, status, bucket)
    return status

def download_job_files(job_id: str, bucket: str) -> int:
    """Download latest job files from GCS to local workspace."""
    from google.cloud import storage
    project_id = os.environ.get("PROJECT_ID")
    storage_client = storage.Client(project=project_id)
    bkt = storage_client.bucket(bucket)
    
    prefix = f"{job_id}/latest/"
    blobs = storage_client.list_blobs(bkt, prefix=prefix)
    
    downloaded = 0
    for blob in blobs:
        if blob.name.endswith("/"):
            continue
        
        # Remove prefix to get local path
        local_path = Path(blob.name.replace(f"{job_id}/latest/", ""))
        local_path.parent.mkdir(parents=True, exist_ok=True)
        
        blob.download_to_filename(str(local_path))
        downloaded += 1
    
    log(f"Downloaded {downloaded} files from gs://{bucket}/{job_id}/latest/")
    return downloaded
    return status
