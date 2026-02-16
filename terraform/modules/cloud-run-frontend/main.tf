# Frontend (Next.js) on Cloud Run.
#
# Unauthenticated in Phase 5A — allUsers invoker. IAP deferred to 5B.
# The $25 billing alert is the safety net until then.

resource "google_cloud_run_v2_service" "frontend" {
  name                = "labsight-frontend-${var.environment}"
  location            = var.region
  project             = var.project_id
  deletion_protection = false

  ingress = "INGRESS_TRAFFIC_ALL"

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
        name  = "NODE_ENV"
        value = "production"
      }

      env {
        name  = "PORT"
        value = "8080"
      }
    }
  }
}

# Unauthenticated access — anyone can reach the frontend.
# IAP will be added in Phase 5B for proper auth.
resource "google_cloud_run_v2_service_iam_member" "public_access" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.frontend.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}
