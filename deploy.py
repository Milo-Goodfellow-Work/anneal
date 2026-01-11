import os
import sys
import tomllib
import subprocess
from pathlib import Path

def run_cmd(cmd: list[str], check: bool = True):
    print(f"Running: {' '.join(cmd)}")
    subprocess.run(cmd, check=check)

def main():
    if not Path("secrets.toml").exists():
        print("Error: secrets.toml not found.")
        sys.exit(1)

    with open("secrets.toml", "rb") as f:
        config = tomllib.load(f)

    openai_key = config.get("secrets", {}).get("OPENAI_API_KEY")
    gcp_conf = config.get("gcp", {})
    project_id = gcp_conf.get("PROJECT_ID")
    region = gcp_conf.get("REGION", "us-central1")
    repo_name = gcp_conf.get("ARTIFACT_REPO", "anneal-repo")
    service_name = gcp_conf.get("SERVICE_NAME", "anneal-worker")

    if not openai_key or "INSERT" in openai_key:
        print("Error: Valid OPENAI_API_KEY required in secrets.toml")
        sys.exit(1)
    if not project_id or "INSERT" in project_id:
        print("Error: Valid GCP PROJECT_ID required in secrets.toml")
        sys.exit(1)

    print(f"Deploying to GCP Project: {project_id} (Region: {region})")

    # 1. Config Project
    run_cmd(["gcloud", "config", "set", "project", project_id])

    # 2. Enable APIs
    print("Enabling APIs...")
    services = [
        "cloudbuild.googleapis.com", 
        "run.googleapis.com", 
        "pubsub.googleapis.com", 
        "artifactregistry.googleapis.com",
        "secretmanager.googleapis.com"
    ]
    run_cmd(["gcloud", "services", "enable"] + services)

    # 3. Create Artifact Repo
    print("Ensuring Artifact Repository...")
    # Check if exists (hacky check via listing or just try create and ignore error)
    # We'll try create and allow failure if it exists
    subprocess.run([
        "gcloud", "artifacts", "repositories", "create", repo_name,
        "--repository-format=docker",
        "--location", region,
        "--description", "Anneal Docker Repository"
    ], check=False)

    # 4. Build & Push
    image_tag = f"{region}-docker.pkg.dev/{project_id}/{repo_name}/worker:latest"
    print(f"Building and Pushing {image_tag}...")
    run_cmd(["gcloud", "builds", "submit", "--tag", image_tag, "."])

    # 5. Create Service Account
    sa_name = f"{service_name}-sa"
    sa_email = f"{sa_name}@{project_id}.iam.gserviceaccount.com"
    print(f"Ensuring Service Account {sa_name}...")
    subprocess.run([
        "gcloud", "iam", "service-accounts", "create", sa_name,
        "--display-name", "Anneal Worker Service Account"
    ], check=False)

    # 6. Deploy Cloud Run
    print("Deploying Cloud Run Service...")
    # Passing API Key as Env Var for prototype simplicity
    run_cmd([
        "gcloud", "run", "deploy", service_name,
        "--image", image_tag,
        "--platform", "managed",
        "--region", region,
        "--service-account", sa_email,
        "--allow-unauthenticated",
        f"--set-env-vars=OPENAI_API_KEY={openai_key}"
    ])

    # 7. Create Pub/Sub Topic
    topic_name = "anneal-jobs"
    print(f"Ensuring Pub/Sub Topic {topic_name}...")
    subprocess.run(["gcloud", "pubsub", "topics", "create", topic_name], check=False)

    # 8. Create Subscription
    sub_name = f"{topic_name}-sub"
    print(f"Ensuring Subscription {sub_name}...")
    
    # Get URL
    res = subprocess.run([
        "gcloud", "run", "services", "describe", service_name,
        "--platform", "managed", "--region", region,
        "--format", "value(status.url)"
    ], capture_output=True, text=True, check=True)
    service_url = res.stdout.strip()
    print(f"Service URL: {service_url}")

    subprocess.run([
        "gcloud", "pubsub", "subscriptions", "create", sub_name,
        "--topic", topic_name,
        "--push-endpoint", service_url,
        "--ack-deadline", "600"
    ], check=False)

    print("\n--------------------------------")
    print("Deployment Complete!")
    print(f"Service URL: {service_url}")
    print("--------------------------------")

if __name__ == "__main__":
    main()
