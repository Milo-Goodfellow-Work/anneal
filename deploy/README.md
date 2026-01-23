# Anneal GCP Deployment

This directory contains everything needed to deploy Anneal to Google Cloud Platform.

## Architecture

- **Cloud Run Jobs**: Ephemeral containers for job processing
- **Pub/Sub**: Job queue
- **Cloud Storage**: Results storage
- **Secret Manager**: API key storage
- **VPC**: Network isolation (no egress)

## Quick Start

### 1. Prerequisites

```bash
# Install gcloud CLI
# Install Terraform
# Authenticate
gcloud auth login
gcloud auth application-default login
```

### 2. Set Up Infrastructure

```bash
cd deploy/terraform

# Initialize Terraform
terraform init

# Create terraform.tfvars
echo 'project_id = "your-project-id"' > terraform.tfvars

# Plan and apply
terraform plan
terraform apply
```

### 3. Add API Keys to Secret Manager

```bash
# Add Gemini API key
echo -n "your-gemini-key" | gcloud secrets versions add anneal-gemini-api-key --data-file=-

# Add Aristotle API key
echo -n "your-aristotle-key" | gcloud secrets versions add anneal-aristotle-api-key --data-file=-
```

### 4. Build and Push Container

```bash
# From repo root
gcloud builds submit --config=deploy/cloudbuild.yaml .
```

### 5. Submit a Job

```bash
# Publish job to Pub/Sub
gcloud pubsub topics publish anneal-jobs --message='{
  "job_id": "test-001",
  "prompt": "Create a memory arena",
  "project_name": "arena",
  "callback_url": ""
}'

# Execute the Cloud Run Job
gcloud run jobs execute anneal-worker \
  --region=us-central1 \
  --update-env-vars="JOB_ID=test-001,PROMPT=Create a memory arena,PROJECT_NAME=arena"
```

## Files

| File | Description |
|------|-------------|
| `Dockerfile.gcp` | Production container image |
| `entrypoint.sh` | Container entrypoint |
| `job_runner.py` | Python job orchestrator |
| `cloudbuild.yaml` | CI/CD configuration |
| `terraform/main.tf` | Infrastructure as Code |

## Security

- Containers have **no internet access** except allowlisted APIs
- API keys stored in Secret Manager
- Each job runs in a fresh, ephemeral container
- All traffic routed through VPC connector
