import os
import json
import uuid
import logging
import asyncio
from typing import Any
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS
from google.cloud import run_v2
from google.cloud import storage

try:
    import aristotlelib
    from aristotlelib import ProjectStatus
except ImportError:
    aristotlelib = None
    ProjectStatus = None

app = Flask(__name__)
CORS(app)  # Enable CORS for frontend access

# Configuration
PROJECT_ID = os.environ.get("PROJECT_ID")
REGION = os.environ.get("REGION", "us-central1")
JOB_NAME = os.environ.get("JOB_NAME", "anneal-job")
BUCKET_NAME = os.environ.get("BUCKET_NAME")

TERMINAL_STATUSES = {"completed", "proof_failed", "verification_failed", "failed"}

# Human-readable status descriptions for the frontend
STATUS_INFO = {
    "queued": {
        "label": "Starting",
        "description": "Your request has been received and is starting...",
        "phase": "setup",
        "progress": 0,
    },
    "running": {
        "label": "Generating Code",
        "description": "AI is generating your implementation with tests and Lean specification...",
        "phase": "generation",
        "progress": 20,
    },
    "proof_submitted": {
        "label": "Beginning Proving",
        "description": "Your code has been submitted to Aristotle for formal verification.",
        "phase": "proving",
        "progress": 40,
    },
    "proof_pending": {
        "label": "Proving",
        "description": "Aristotle is working on formally proving your code...",
        "phase": "proving",
        "progress": 50,
    },
    "verifying": {
        "label": "Verifying",
        "description": "Running final verification with the completed proof...",
        "phase": "verification",
        "progress": 80,
    },
    "completed": {
        "label": "Verification Complete",
        "description": "Your code has been formally verified and is ready for download.",
        "phase": "done",
        "progress": 100,
    },
    "proof_failed": {
        "label": "Proof Failed",
        "description": "Aristotle could not prove the code automatically. You can still download the draft implementation.",
        "phase": "error",
        "progress": None,
    },
    "verification_failed": {
        "label": "Verification Failed",
        "description": "The final verification step encountered an error. The draft is still available.",
        "phase": "error",
        "progress": None,
    },
    "failed": {
        "label": "Failed",
        "description": "An error occurred during processing. Please try again.",
        "phase": "error",
        "progress": None,
    },
}

# Aristotle status descriptions
ARISTOTLE_STATUS_INFO = {
    "NOT_STARTED": {"label": "Not Started", "description": "Proof request created but not yet queued."},
    "QUEUED": {"label": "Queued", "description": "Your proof is in Aristotle's queue."},
    "IN_PROGRESS": {"label": "In Progress", "description": "Aristotle is actively working on the proof."},
    "COMPLETE": {"label": "Complete", "description": "Aristotle has finished the proof."},
    "FAILED": {"label": "Failed", "description": "Aristotle encountered an error."},
    "PENDING_RETRY": {"label": "Retrying", "description": "Aristotle is retrying after a temporary error."},
}

def _enrich_job_status(job: dict) -> dict:
    """Add human-readable status info to job dict."""
    status = job.get("status", "unknown")
    info = STATUS_INFO.get(status, {
        "label": status.replace("_", " ").title(),
        "description": "Status unknown.",
        "phase": "unknown",
        "progress": None,
    })
    job["status_info"] = info

    aristotle_status = job.get("aristotle_status")
    if aristotle_status:
        aristotle_info = ARISTOTLE_STATUS_INFO.get(aristotle_status, {
            "label": aristotle_status.replace("_", " ").title(),
            "description": "Unknown Aristotle status.",
        })
        job["aristotle_status_info"] = aristotle_info

    return job

# Clients - Lazy initialized
def get_clients():
    project_id = os.environ.get("PROJECT_ID")
    if not project_id:
        raise ValueError("PROJECT_ID env var not set")
    return storage.Client(project=project_id), run_v2.JobsClient()

def _load_job(bucket, job_id: str) -> dict | None:
    blob = bucket.blob(f"jobs/{job_id}.json")
    if not blob.exists():
        return None
    return json.loads(blob.download_as_text())

def _save_job(bucket, job_id: str, job: dict) -> None:
    job["updated_at"] = datetime.now().isoformat()
    bucket.blob(f"jobs/{job_id}.json").upload_from_string(json.dumps(job, indent=2), content_type="application/json")

def _get_public_base_url() -> str:
    """Resolve base URL for callbacks, preferring PUBLIC_BASE_URL env var."""
    base = os.environ.get("PUBLIC_BASE_URL")
    if base:
        return base.rstrip("/")
    return request.url_root.rstrip("/")

def _trigger_job(job_id: str, mode: str, extra_env: list[dict] | None = None) -> None:
    if not PROJECT_ID:
        raise ValueError("PROJECT_ID env var not set")

    _, run_client = get_clients()
    job_path = f"projects/{PROJECT_ID}/locations/{REGION}/jobs/{JOB_NAME}"

    env = [
        {"name": "JOB_ID", "value": job_id},
        {"name": "RESULTS_BUCKET", "value": BUCKET_NAME},
        {"name": "JOB_MODE", "value": mode},
    ]
    if extra_env:
        env.extend(extra_env)

    overrides = {"container_overrides": [{"env": env}]}
    request_obj = run_v2.RunJobRequest(name=job_path, overrides=overrides)
    run_client.run_job(request=request_obj)

async def _get_aristotle_status(aristotle_id: str) -> str:
    if aristotlelib is None:
        return "MISSING_LIB"
    project = await aristotlelib.Project.from_id(aristotle_id)
    await project.refresh()
    status = project.status
    if ProjectStatus is not None:
        return status.value
    return str(status).split(".")[-1]

@app.route("/", methods=["GET"])
def health_check():
    return jsonify({"status": "running"}), 200

@app.route("/submit", methods=["POST"])
def submit_job():
    """
    Submit a new job.
    Payload: {"prompt": "str"}
    Returns: {"job_id": "str"}
    """
    data = request.get_json()
    if not data or "prompt" not in data:
        return jsonify({"error": "Missing 'prompt' in payload"}), 400

    job_id = str(uuid.uuid4())
    prompt = data["prompt"]
    
    bucket_name = os.environ.get("BUCKET_NAME")
    if not bucket_name:
         return jsonify({"error": "BUCKET_NAME env var not set"}), 500

    callback_url = f"{_get_public_base_url()}/notify/fire/{job_id}"
    initial_state = {
        "job_id": job_id,
        "prompt": prompt,
        "status": "queued",
        "created_at": datetime.now().isoformat(),
        "aristotle_id": None,
        "aristotle_status": None,
        "proof_verified": False,
        "callback_url": callback_url,
        "push_subscriptions": [],
    }
         
    storage_client, _ = get_clients()
    
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(f"jobs/{job_id}.json")
    blob.upload_from_string(json.dumps(initial_state), content_type="application/json")
    
    # 2. Trigger Cloud Run Job
    if os.environ.get("LOCAL_MODE"):
        app.logger.info(f"LOCAL_MODE enabled: Skipping Cloud Run trigger for job {job_id}")
        return jsonify({"job_id": job_id, "status": "queued", "mode": "local"}), 202

    if not PROJECT_ID:
         return jsonify({"error": "PROJECT_ID env var not set"}), 500

    try:
        _trigger_job(job_id, "prove")
    except Exception as e:
        app.logger.error(f"Failed to trigger job: {e}")
        return jsonify({"error": str(e)}), 500

    return jsonify({"job_id": job_id, "status": "queued"}), 202

@app.route("/status/<job_id>", methods=["GET"])
def get_status(job_id):
    """
    Get job status from GCS.
    """
    bucket_name = os.environ.get("BUCKET_NAME")
    if not bucket_name:
        return jsonify({"error": "BUCKET_NAME env var not set"}), 500

    storage_client, _ = get_clients()
    bucket = storage_client.bucket(bucket_name)
    job = _load_job(bucket, job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404

    include_aristotle = request.args.get("include_aristotle", "false").lower() == "true"
    if include_aristotle and job.get("aristotle_id"):
        try:
            status = asyncio.run(_get_aristotle_status(job["aristotle_id"]))
            job["aristotle_status"] = status
        except Exception as e:
            job["aristotle_status_error"] = str(e)

    return jsonify(_enrich_job_status(job))

@app.route("/aristotle/<job_id>", methods=["GET"])
def get_aristotle_status(job_id):
    bucket_name = os.environ.get("BUCKET_NAME")
    if not bucket_name:
        return jsonify({"error": "BUCKET_NAME env var not set"}), 500

    storage_client, _ = get_clients()
    bucket = storage_client.bucket(bucket_name)
    job = _load_job(bucket, job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404
    if not job.get("aristotle_id"):
        return jsonify({"error": "Job has no aristotle_id"}), 400

    try:
        status = asyncio.run(_get_aristotle_status(job["aristotle_id"]))
        return jsonify({"job_id": job_id, "aristotle_id": job["aristotle_id"], "aristotle_status": status})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/files/<job_id>", methods=["GET"])
def list_files(job_id):
    bucket_name = os.environ.get("BUCKET_NAME")
    if not bucket_name:
        return jsonify({"error": "BUCKET_NAME env var not set"}), 500

    storage_client, _ = get_clients()
    bucket = storage_client.bucket(bucket_name)
    prefix = f"{job_id}/latest/"
    blobs = storage_client.list_blobs(bucket, prefix=prefix)

    files = []
    for b in blobs:
        if b.name.endswith("/"):
            continue
        files.append({"path": b.name, "gs_uri": f"gs://{bucket_name}/{b.name}"})

    return jsonify({"job_id": job_id, "files": files})

@app.route("/jobs", methods=["GET"])
def list_jobs():
    """
    List all jobs from GCS with enriched status.
    Query params:
      - limit: max number of jobs (default 50)
      - status: filter by status
    """
    bucket_name = os.environ.get("BUCKET_NAME")
    if not bucket_name:
        return jsonify({"error": "BUCKET_NAME env var not set"}), 500

    storage_client, _ = get_clients()
    bucket = storage_client.bucket(bucket_name)
    blobs = storage_client.list_blobs(bucket, prefix="jobs/")

    limit = request.args.get("limit", 50, type=int)
    status_filter = request.args.get("status")

    jobs = []
    for blob in blobs:
        if not blob.name.endswith(".json"):
            continue

        job_id = blob.name.split("/")[-1].replace(".json", "")
        job = _load_job(bucket, job_id)
        if not job:
            continue

        enriched = _enrich_job_status(job)
        
        if status_filter and enriched.get("status") != status_filter:
            continue

        jobs.append(enriched)
        if len(jobs) >= limit:
            break

    # Sort by created_at descending (newest first)
    jobs.sort(key=lambda j: j.get("created_at", ""), reverse=True)

    return jsonify({"jobs": jobs, "count": len(jobs)})

@app.route("/files/<job_id>/download", methods=["GET"])
def download_files(job_id):
    """
    Download all files for a job as a ZIP archive.
    """
    import io
    import zipfile

    bucket_name = os.environ.get("BUCKET_NAME")
    if not bucket_name:
        return jsonify({"error": "BUCKET_NAME env var not set"}), 500

    storage_client, _ = get_clients()
    bucket = storage_client.bucket(bucket_name)
    prefix = f"{job_id}/latest/"
    blobs = list(storage_client.list_blobs(bucket, prefix=prefix))

    if not blobs:
        return jsonify({"error": "No files found for job"}), 404

    # Create in-memory ZIP
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for blob in blobs:
            if blob.name.endswith("/"):
                continue
            # Strip prefix to get relative path
            rel_path = blob.name[len(prefix):]
            content = blob.download_as_bytes()
            zf.writestr(rel_path, content)

    zip_buffer.seek(0)

    from flask import send_file
    return send_file(
        zip_buffer,
        mimetype="application/zip",
        as_attachment=True,
        download_name=f"{job_id}.zip"
    )

@app.route("/files/<job_id>/<path:filepath>", methods=["GET"])
def get_file(job_id, filepath):
    """
    Get a single file's content from a job.
    """
    bucket_name = os.environ.get("BUCKET_NAME")
    if not bucket_name:
        return jsonify({"error": "BUCKET_NAME env var not set"}), 500

    storage_client, _ = get_clients()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(f"{job_id}/latest/{filepath}")

    if not blob.exists():
        return jsonify({"error": "File not found"}), 404

    content = blob.download_as_text()
    
    # Determine content type
    if filepath.endswith(".lean"):
        content_type = "text/plain"
    elif filepath.endswith(".json"):
        content_type = "application/json"
    elif filepath.endswith(".c"):
        content_type = "text/x-c"
    else:
        content_type = "text/plain"

    return content, 200, {"Content-Type": content_type}

@app.route("/poll", methods=["POST"])
def poll_jobs():
    print(f"[POLL] Received request", flush=True)
    
    bucket_name = os.environ.get("BUCKET_NAME")
    if not bucket_name:
        print(f"[POLL] Error: BUCKET_NAME not set", flush=True)
        return jsonify({"error": "BUCKET_NAME env var not set"}), 500

    storage_client, _ = get_clients()
    bucket = storage_client.bucket(bucket_name)
    blobs = storage_client.list_blobs(bucket, prefix="jobs/")

    processed = 0
    triggered = 0
    for blob in blobs:
        if not blob.name.endswith(".json"):
            continue

        job_id = blob.name.split("/")[-1].replace(".json", "")
        job = _load_job(bucket, job_id)
        if not job:
            continue

        status = job.get("status", "")
        if status in {"completed", "failed", "verification_failed", "proof_failed"}:
            continue

        aristotle_id = job.get("aristotle_id")
        if not aristotle_id:
            continue

        try:
            aristotle_status = asyncio.run(_get_aristotle_status(aristotle_id))
        except Exception as e:
            app.logger.error(f"Aristotle status error for {job_id}: {e}")
            continue

        job["aristotle_status"] = aristotle_status

        if aristotle_status == "COMPLETE":
            if status != "verifying":
                try:
                    _trigger_job(job_id, "verify", extra_env=[{"name": "ARISTOTLE_ID", "value": aristotle_id}])
                    job["status"] = "verifying"
                    triggered += 1
                except Exception as e:
                    app.logger.error(f"Failed to trigger verify job for {job_id}: {e}")
        elif aristotle_status in {"FAILED"}:
            job["status"] = "proof_failed"
        else:
            if status not in {"verifying"}:
                job["status"] = "proof_pending"

        _save_job(bucket, job_id, job)
        processed += 1

    # Force stdout logging for visibility
    print(f"[POLL] Processed={processed}, Triggered={triggered}", flush=True) 
    return jsonify({"processed": processed, "triggered": triggered})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
