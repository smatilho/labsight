# Frontend (Next.js) on Cloud Run.
#
# Phase 5A: allUsers invoker (frontend_public = true).
# Phase 5B: IAP-protected (frontend_public = false, default).
#
# When frontend_public = false, ingress is set to allow internal + LB traffic
# so the HTTPS load balancer (IAP module) can reach the service.

resource "google_cloud_run_v2_service" "frontend" {
  name                = "labsight-frontend-${var.environment}"
  location            = var.region
  project             = var.project_id
  deletion_protection = false

  ingress = var.frontend_public ? "INGRESS_TRAFFIC_ALL" : "INGRESS_TRAFFIC_INTERNAL_LOAD_BALANCER"

  template {
    execution_environment = "EXECUTION_ENVIRONMENT_GEN2"

    scaling {
      min_instance_count = 0
      max_instance_count = 2
    }

    service_account = var.frontend_sa_email

    containers {
      image = var.image

      ports {
        container_port = 8080
      }

      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
      }

      env {
        name  = "BACKEND_URL"
        value = var.backend_url
      }

      env {
        name  = "BACKEND_AUTH_MODE"
        value = var.backend_auth_mode
      }

      env {
        name  = "NODE_ENV"
        value = "production"
      }

      # API key from Secret Manager (only when using api_key auth mode)
      dynamic "env" {
        for_each = var.backend_auth_mode == "api_key" && var.api_key_secret_id != "" ? [1] : []
        content {
          name = "BACKEND_API_KEY"
          value_source {
            secret_key_ref {
              secret  = var.api_key_secret_id
              version = "latest"
            }
          }
        }
      }
    }
  }
}

# Public access — only when explicitly enabled (Phase 5A compat).
resource "google_cloud_run_v2_service_iam_member" "public_access" {
  count    = var.frontend_public ? 1 : 0
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.frontend.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}
