# Anneal GCP Infrastructure
#
# This Terraform configuration creates:
# - VPC with no egress (isolated network)
# - Pub/Sub topic and subscription for job queue
# - Cloud Storage bucket for results
# - Secret Manager secrets for API keys
# - Cloud Run Job for processing
# - Serverless VPC connector

terraform {
  required_version = ">= 1.0"
  
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
  
  # Store state in GCS (update bucket name)
  backend "gcs" {
    bucket = "anneal-terraform-state"
    prefix = "terraform/state"
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# Variables
variable "project_id" {
  description = "GCP Project ID"
  type        = string
}

variable "region" {
  description = "GCP Region"
  type        = string
  default     = "us-central1"
}

# ============================================================
# VPC - Isolated Network with No Egress
# ============================================================

resource "google_compute_network" "anneal_vpc" {
  name                    = "anneal-isolated-vpc"
  auto_create_subnetworks = false
  description             = "Isolated VPC for Anneal job processing - no internet egress"
}

resource "google_compute_subnetwork" "anneal_subnet" {
  name          = "anneal-subnet"
  ip_cidr_range = "10.0.0.0/24"
  region        = var.region
  network       = google_compute_network.anneal_vpc.id
  
  # Enable Private Google Access for GCP APIs
  private_ip_google_access = true
}

# Firewall - Deny all egress except to GCP APIs
resource "google_compute_firewall" "deny_all_egress" {
  name    = "anneal-deny-all-egress"
  network = google_compute_network.anneal_vpc.name
  
  direction = "EGRESS"
  priority  = 1000
  
  deny {
    protocol = "all"
  }
  
  destination_ranges = ["0.0.0.0/0"]
}

# Allow egress to Google APIs only (via Private Google Access)
resource "google_compute_firewall" "allow_google_apis" {
  name    = "anneal-allow-google-apis"
  network = google_compute_network.anneal_vpc.name
  
  direction = "EGRESS"
  priority  = 100
  
  allow {
    protocol = "tcp"
    ports    = ["443"]
  }
  
  # Google's private API ranges
  destination_ranges = [
    "199.36.153.8/30",   # private.googleapis.com
    "199.36.153.4/30",   # restricted.googleapis.com
  ]
}

# Serverless VPC Connector for Cloud Run
resource "google_vpc_access_connector" "anneal_connector" {
  name          = "anneal-vpc-connector"
  region        = var.region
  network       = google_compute_network.anneal_vpc.name
  ip_cidr_range = "10.8.0.0/28"
  
  min_instances = 2
  max_instances = 3
}

# ============================================================
# Pub/Sub - Job Queue
# ============================================================

resource "google_pubsub_topic" "anneal_jobs" {
  name = "anneal-jobs"
}

resource "google_pubsub_topic" "anneal_jobs_dlq" {
  name = "anneal-jobs-dlq"
}

resource "google_pubsub_subscription" "anneal_jobs_sub" {
  name  = "anneal-jobs-subscription"
  topic = google_pubsub_topic.anneal_jobs.name
  
  ack_deadline_seconds = 600  # 10 minutes
  
  dead_letter_policy {
    dead_letter_topic     = google_pubsub_topic.anneal_jobs_dlq.id
    max_delivery_attempts = 3
  }
  
  retry_policy {
    minimum_backoff = "10s"
    maximum_backoff = "600s"
  }
}

# ============================================================
# Cloud Storage - Results Bucket
# ============================================================

resource "google_storage_bucket" "anneal_results" {
  name          = "${var.project_id}-anneal-results"
  location      = var.region
  force_destroy = false
  
  uniform_bucket_level_access = true
  
  lifecycle_rule {
    condition {
      age = 30  # Delete after 30 days
    }
    action {
      type = "Delete"
    }
  }
}

# ============================================================
# Secret Manager - API Keys
# ============================================================

resource "google_secret_manager_secret" "gemini_api_key" {
  secret_id = "anneal-gemini-api-key"
  
  replication {
    auto {}
  }
}

resource "google_secret_manager_secret" "aristotle_api_key" {
  secret_id = "anneal-aristotle-api-key"
  
  replication {
    auto {}
  }
}

# ============================================================
# Artifact Registry - Container Images
# ============================================================

resource "google_artifact_registry_repository" "anneal" {
  location      = var.region
  repository_id = "anneal"
  description   = "Anneal container images"
  format        = "DOCKER"
}

# ============================================================
# Cloud Run Job - Worker
# ============================================================

resource "google_cloud_run_v2_job" "anneal_worker" {
  name     = "anneal-worker"
  location = var.region
  
  template {
    template {
      containers {
        image = "${var.region}-docker.pkg.dev/${var.project_id}/anneal/anneal:latest"
        
        resources {
          limits = {
            cpu    = "2"
            memory = "4Gi"
          }
        }
        
        # Secrets as environment variables
        env {
          name = "GEMINI_API_KEY"
          value_source {
            secret_key_ref {
              secret  = google_secret_manager_secret.gemini_api_key.secret_id
              version = "latest"
            }
          }
        }
        
        env {
          name = "ARISTOTLE_API_KEY"
          value_source {
            secret_key_ref {
              secret  = google_secret_manager_secret.aristotle_api_key.secret_id
              version = "latest"
            }
          }
        }
        
        env {
          name  = "RESULTS_BUCKET"
          value = google_storage_bucket.anneal_results.name
        }
      }
      
      # VPC connector for network isolation
      vpc_access {
        connector = google_vpc_access_connector.anneal_connector.id
        egress    = "ALL_TRAFFIC"
      }
      
      timeout     = "3600s"  # 1 hour max
      max_retries = 0        # Don't retry - dead letter instead
    }
    
    parallelism = 10  # Max concurrent jobs
    task_count  = 1   # One task per execution
  }
}

# IAM - Allow Cloud Run to access secrets
resource "google_secret_manager_secret_iam_member" "gemini_access" {
  secret_id = google_secret_manager_secret.gemini_api_key.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_cloud_run_v2_job.anneal_worker.template[0].template[0].service_account}"
}

resource "google_secret_manager_secret_iam_member" "aristotle_access" {
  secret_id = google_secret_manager_secret.aristotle_api_key.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_cloud_run_v2_job.anneal_worker.template[0].template[0].service_account}"
}

# IAM - Allow Cloud Run to write to GCS
resource "google_storage_bucket_iam_member" "results_writer" {
  bucket = google_storage_bucket.anneal_results.name
  role   = "roles/storage.objectCreator"
  member = "serviceAccount:${google_cloud_run_v2_job.anneal_worker.template[0].template[0].service_account}"
}

# ============================================================
# Outputs
# ============================================================

output "job_queue_topic" {
  value = google_pubsub_topic.anneal_jobs.id
}

output "results_bucket" {
  value = google_storage_bucket.anneal_results.url
}

output "cloud_run_job" {
  value = google_cloud_run_v2_job.anneal_worker.name
}

output "vpc_connector" {
  value = google_vpc_access_connector.anneal_connector.name
}
