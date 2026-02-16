# API Gateway for the Labsight RAG backend.
#
# Routes frontend requests to the RAG service with API key validation
# and backend auth via a dedicated gateway SA. The gateway SA gets
# roles/run.invoker on the RAG service (managed in cloud-run-rag module).
#
# Frontend sends x-api-key header; gateway validates it, then forwards
# the request with a JWT signed by the gateway SA.

locals {
  rendered_openapi = templatefile(
    "${path.module}/openapi.yaml.tmpl",
    { backend_url = var.backend_url }
  )

  # Include gateway SA in the hash so create_before_destroy can always
  # create a distinct config ID when auth wiring changes.
  api_config_hash = substr(
    sha256(
      jsonencode({
        openapi_doc      = local.rendered_openapi
        gateway_sa_email = var.gateway_sa_email
      })
    ),
    0,
    8
  )
}

# --- API resource ---

resource "google_api_gateway_api" "labsight" {
  provider = google-beta
  api_id   = "labsight-api-${var.environment}"
  project  = var.project_id
}

# Ensure the managed API service is enabled for the project so
# API key-authenticated calls do not fail with PERMISSION_DENIED.
resource "google_project_service" "managed_gateway_service" {
  project = var.project_id
  service = google_api_gateway_api.labsight.managed_service

  # Keep service enabled when destroying this stack to avoid
  # intermittent teardown errors and broken re-apply sequences.
  disable_on_destroy = false
}

# --- OpenAPI config ---

resource "google_api_gateway_api_config" "labsight" {
  provider      = google-beta
  api           = google_api_gateway_api.labsight.api_id
  api_config_id = "labsight-config-${var.environment}-${local.api_config_hash}"
  project       = var.project_id

  openapi_documents {
    document {
      path     = "openapi.yaml"
      contents = base64encode(local.rendered_openapi)
    }
  }

  gateway_config {
    backend_config {
      google_service_account = var.gateway_sa_email
    }
  }

  lifecycle {
    create_before_destroy = true
  }

  depends_on = [google_project_service.managed_gateway_service]
}

# --- Gateway instance ---

resource "google_api_gateway_gateway" "labsight" {
  provider   = google-beta
  gateway_id = "labsight-gateway-${var.environment}"
  api_config = google_api_gateway_api_config.labsight.id
  project    = var.project_id
  region     = var.region
}

# --- API key restricted to this gateway ---

resource "google_apikeys_key" "frontend" {
  # Use a versioned key ID so we can recover cleanly if a previously-deleted
  # key ID is still reserved by the API Keys control plane.
  name         = "labsight-frontend-key-${var.environment}-v2"
  display_name = "Labsight Frontend API Key"
  project      = var.project_id

  restrictions {
    api_targets {
      service = google_api_gateway_api.labsight.managed_service
    }
  }
}

# --- Store API key in Secret Manager ---

resource "google_secret_manager_secret" "api_key" {
  secret_id = "labsight-gateway-api-key-${var.environment}"
  project   = var.project_id

  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "api_key" {
  secret      = google_secret_manager_secret.api_key.id
  secret_data = google_apikeys_key.frontend.key_string
}

# --- Frontend SA can read the API key secret ---

resource "google_secret_manager_secret_iam_member" "frontend_api_key_accessor" {
  secret_id = google_secret_manager_secret.api_key.id
  project   = var.project_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${var.frontend_sa_email}"
}
