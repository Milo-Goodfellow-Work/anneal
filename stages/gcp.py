#!/usr/bin/env python3
"""GCP Integration - Job storage and results upload."""
import json
from pathlib import Path
from datetime import datetime
from typing import Optional
from helpers import log

def fetch_job_params(job_id: str, bucket: str) -> dict:
    """Fetch job params from gs://bucket/jobs/{job_id}.json"""
    from google.cloud import storage
    blob = storage.Client().bucket(bucket).blob(f"jobs/{job_id}.json")
    params = json.loads(blob.download_as_text())
    if "prompt" not in params:
        raise ValueError(f"Job {job_id} missing prompt")
    return params

def update_job_status(job_id: str, bucket: str, status: str, error: Optional[str] = None) -> dict:
    """Update job status in GCS."""
    from google.cloud import storage
    blob = storage.Client().bucket(bucket).blob(f"jobs/{job_id}.json")
    params = json.loads(blob.download_as_text())
    params["status"] = status
    params["updated_at"] = datetime.now().isoformat()
    if status == "running":
        params["started_at"] = datetime.now().isoformat()
    elif status in ("completed", "failed"):
        params["finished_at"] = datetime.now().isoformat()
        if error: params["error"] = error
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
    bkt = storage.Client().bucket(bucket)
    files = _collect_files()
    for f in files:
        bkt.blob(f"{job_id}/{f}").upload_from_filename(str(f))
    status = {"job_id": job_id, "status": "completed" if success else "failed",
              "files_uploaded": len(files), "completed_at": datetime.now().isoformat()}
    bkt.blob(f"{job_id}/status.json").upload_from_string(json.dumps(status, indent=2))
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
