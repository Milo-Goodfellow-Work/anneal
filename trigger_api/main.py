import os
import json
import uuid
import logging
from flask import Flask, request, jsonify
from google.cloud import run_v2
from google.cloud import storage

app = Flask(__name__)

# Configuration
PROJECT_ID = os.environ.get("PROJECT_ID")
REGION = os.environ.get("REGION", "us-central1")
JOB_NAME = os.environ.get("JOB_NAME", "anneal-job")
BUCKET_NAME = os.environ.get("BUCKET_NAME")

# Clients - Lazy initialized
def get_clients():
    project_id = os.environ.get("PROJECT_ID")
    if not project_id:
        raise ValueError("PROJECT_ID env var not set")
    return storage.Client(project=project_id), run_v2.JobsClient()

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

    initial_state = {
        "job_id": job_id,
        "prompt": prompt,
        "status": "queued",
        "created_at": "now", # Placeholder, ideally use isoformat
        "aristotle_id": None
    }
         
    storage_client, run_client = get_clients()
    
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(f"jobs/{job_id}.json")
    blob.upload_from_string(json.dumps(initial_state), content_type="application/json")
    
    # 2. Trigger Cloud Run Job
    if os.environ.get("LOCAL_MODE"):
        app.logger.info(f"LOCAL_MODE enabled: Skipping Cloud Run trigger for job {job_id}")
        return jsonify({"job_id": job_id, "status": "queued", "mode": "local"}), 202

    if not PROJECT_ID:
         return jsonify({"error": "PROJECT_ID env var not set"}), 500

    job_path = f"projects/{PROJECT_ID}/locations/{REGION}/jobs/{JOB_NAME}"
    
    overrides = {
        "container_overrides": [
            {
                "env": [
                    {"name": "JOB_ID", "value": job_id},
                    {"name": "RESULTS_BUCKET", "value": BUCKET_NAME}
                ]
            }
        ]
    }

    request_obj = run_v2.RunJobRequest(
        name=job_path,
        overrides=overrides
    )

    try:
        operation = run_client.run_job(request=request_obj)
        # We don't wait for completion, just trigger
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
    blob = bucket.blob(f"jobs/{job_id}.json")
    
    if not blob.exists():
        return jsonify({"error": "Job not found"}), 404
        
    try:
        content = blob.download_as_text()
        return jsonify(json.loads(content))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
