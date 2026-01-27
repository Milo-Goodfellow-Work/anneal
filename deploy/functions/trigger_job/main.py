"""
Cloud Function: Trigger Anneal Job

Triggered by Pub/Sub messages containing job_id.
Executes Cloud Run Job with JOB_ID env var.
"""
import base64
import os
import functions_framework
from google.cloud import run_v2


PROJECT_ID = os.environ.get("GCP_PROJECT", "")
REGION = os.environ.get("REGION", "us-central1")
JOB_NAME = os.environ.get("JOB_NAME", "anneal-worker")
RESULTS_BUCKET = os.environ.get("RESULTS_BUCKET", "")


@functions_framework.cloud_event
def trigger_anneal_job(cloud_event):
    """Pub/Sub trigger - executes Cloud Run Job with JOB_ID."""
    
    # Decode job_id from Pub/Sub message
    job_id = base64.b64decode(cloud_event.data["message"]["data"]).decode("utf-8").strip()
    
    print(f"Received job trigger for: {job_id}")
    
    if not job_id:
        print("ERROR: Empty job_id received")
        return
    
    # Execute Cloud Run Job
    client = run_v2.JobsClient()
    job_path = f"projects/{PROJECT_ID}/locations/{REGION}/jobs/{JOB_NAME}"
    
    print(f"Executing Cloud Run Job: {job_path}")
    print(f"  JOB_ID={job_id}")
    print(f"  RESULTS_BUCKET={RESULTS_BUCKET}")
    
    # Build the execution request with env var overrides
    request = run_v2.RunJobRequest(
        name=job_path,
        overrides=run_v2.RunJobRequest.Overrides(
            container_overrides=[
                run_v2.RunJobRequest.Overrides.ContainerOverride(
                    env=[
                        run_v2.EnvVar(name="JOB_ID", value=job_id),
                        run_v2.EnvVar(name="RESULTS_BUCKET", value=RESULTS_BUCKET),
                    ]
                )
            ]
        ),
    )
    
    # Execute (async - don't wait for completion)
    operation = client.run_job(request=request)
    
    print(f"Job execution started: {operation.operation.name}")
    return {"status": "triggered", "job_id": job_id}
