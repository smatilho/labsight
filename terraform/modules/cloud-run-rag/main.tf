# RAG service on Cloud Run.
#
# Why Cloud Run instead of GKE?
# - GKE Autopilot cluster management fee is ~$72/month (nearly 3x the $25
#   billing alert). Cloud Run scales to zero with $0 idle cost.
# - Cloud Run is already proven (ChromaDB runs on it).
# - The service is containerized either way — moving to GKE later is a
#   Terraform module swap, not a code change.
#
# Auth: Cloud Run IAM. Only the deployer's identity (or IAP in Phase 5)
# can invoke the service.

# --- Secret Manager for OpenRouter API key ---
# Only created when an API key is provided (openrouter mode). When using
# Vertex AI only, no secret is needed and the env var stays empty.

resource "google_secret_manager_secret" "openrouter_api_key" {
  count     = var.openrouter_api_key != "" ? 1 : 0
  secret_id = "labsight-openrouter-api-key-${var.environment}"
  project   = var.project_id

  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "openrouter_api_key" {
  count       = var.openrouter_api_key != "" ? 1 : 0
  secret      = google_secret_manager_secret.openrouter_api_key[0].id
  secret_data = var.openrouter_api_key
}

resource "google_secret_manager_secret_iam_member" "rag_secret_accessor" {
  count     = var.openrouter_api_key != "" ? 1 : 0
  secret_id = google_secret_manager_secret.openrouter_api_key[0].id
  project   = var.project_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${var.rag_service_sa_email}"
}

resource "google_cloud_run_v2_service" "rag_service" {
  name                = "labsight-rag-${var.environment}"
  location            = var.region
  project             = var.project_id
  deletion_protection = false

  # INGRESS_TRAFFIC_ALL because API Gateway / frontend (Phase 5) will
  # route through the public internet. Security is enforced by IAM.
  ingress = "INGRESS_TRAFFIC_ALL"

  template {
    execution_environment = "EXECUTION_ENVIRONMENT_GEN2"

    scaling {
      min_instance_count = 0
      max_instance_count = 2
    }

    service_account = var.rag_service_sa_email

    containers {
      image = var.image

      ports {
        container_port = 8080
      }

      resources {
        limits = {
          cpu    = "1"
          memory = "1Gi"
        }
      }

      # Application configuration via env vars (LABSIGHT_ prefix)
      env {
        name  = "LABSIGHT_GCP_PROJECT"
        value = var.project_id
      }
      env {
        name  = "LABSIGHT_GCP_REGION"
        value = var.region
      }
      env {
        name  = "LABSIGHT_CHROMADB_URL"
        value = var.chromadb_url
      }
      env {
        name  = "LABSIGHT_LLM_PROVIDER"
        value = var.llm_provider
      }

      # OpenRouter API key: pulled from Secret Manager when configured,
      # otherwise set to empty string (Vertex AI only mode).
      dynamic "env" {
        for_each = var.openrouter_api_key != "" ? [1] : []
        content {
          name = "LABSIGHT_OPENROUTER_API_KEY"
          value_source {
            secret_key_ref {
              secret  = google_secret_manager_secret.openrouter_api_key[0].secret_id
              version = "latest"
            }
          }
        }
      }
      dynamic "env" {
        for_each = var.openrouter_api_key == "" ? [1] : []
        content {
          name  = "LABSIGHT_OPENROUTER_API_KEY"
          value = ""
        }
      }

      env {
        name  = "LABSIGHT_BIGQUERY_QUERY_LOG_TABLE"
        value = var.bigquery_query_log_table
      }

      env {
        name  = "LABSIGHT_BIGQUERY_METRICS_DATASET"
        value = var.bigquery_metrics_dataset
      }

      env {
        name  = "LABSIGHT_GCS_UPLOADS_BUCKET"
        value = var.gcs_uploads_bucket
      }

      env {
        name  = "LABSIGHT_BIGQUERY_OBSERVABILITY_DATASET"
        value = var.bigquery_observability_dataset
      }
    }
  }
}

# --- Phase 5: Frontend SA invoker binding ---
# Kept in the RAG module so all RAG service IAM lives in one place.

resource "google_cloud_run_v2_service_iam_member" "frontend_invoker" {
  count    = var.frontend_sa_email != "" ? 1 : 0
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.rag_service.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${var.frontend_sa_email}"
}
