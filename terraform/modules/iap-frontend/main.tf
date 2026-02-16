# IAP edge for the frontend Cloud Run service.
#
# Creates a global HTTPS load balancer with a managed SSL certificate
# and Identity-Aware Proxy. Only members listed in var.iap_members
# can access the frontend.
#
# Prerequisites (manual, one-time):
#   1. Configure OAuth consent screen in GCP Console
#      (APIs & Services > OAuth consent screen > External > add test user)
#   2. Add a DNS A record for var.domain pointing to the static IP output
#
# IAP auto-creates its OAuth client when enabled on the backend service.

# --- Static IP for DNS ---

resource "google_compute_global_address" "frontend" {
  name    = "labsight-frontend-ip-${var.environment}"
  project = var.project_id
}

# --- Managed SSL certificate ---

resource "google_compute_managed_ssl_certificate" "frontend" {
  name    = "labsight-frontend-cert-${var.environment}"
  project = var.project_id

  managed {
    domains = [var.domain]
  }
}

# --- Serverless NEG pointing to the Cloud Run service ---

resource "google_compute_region_network_endpoint_group" "frontend" {
  name                  = "labsight-frontend-neg-${var.environment}"
  project               = var.project_id
  region                = var.region
  network_endpoint_type = "SERVERLESS"

  cloud_run {
    service = var.frontend_service_name
  }
}

# --- Backend service with IAP enabled ---

resource "google_compute_backend_service" "frontend" {
  name    = "labsight-frontend-backend-${var.environment}"
  project = var.project_id

  protocol              = "HTTPS"
  load_balancing_scheme = "EXTERNAL_MANAGED"
  timeout_sec           = 30

  backend {
    group = google_compute_region_network_endpoint_group.frontend.id
  }

  iap {
    enabled = true
  }
}

# --- URL map (all traffic to the one backend) ---

resource "google_compute_url_map" "frontend" {
  name            = "labsight-frontend-urlmap-${var.environment}"
  project         = var.project_id
  default_service = google_compute_backend_service.frontend.id
}

# --- HTTPS proxy ---

resource "google_compute_target_https_proxy" "frontend" {
  name    = "labsight-frontend-https-proxy-${var.environment}"
  project = var.project_id
  url_map = google_compute_url_map.frontend.id

  ssl_certificates = [google_compute_managed_ssl_certificate.frontend.id]
}

# --- Forwarding rule ---

resource "google_compute_global_forwarding_rule" "frontend" {
  name       = "labsight-frontend-https-${var.environment}"
  project    = var.project_id
  target     = google_compute_target_https_proxy.frontend.id
  port_range = "443"
  ip_address = google_compute_global_address.frontend.address

  load_balancing_scheme = "EXTERNAL_MANAGED"
}

# --- HTTP-to-HTTPS redirect ---

resource "google_compute_url_map" "http_redirect" {
  name    = "labsight-frontend-http-redirect-${var.environment}"
  project = var.project_id

  default_url_redirect {
    https_redirect         = true
    strip_query            = false
    redirect_response_code = "MOVED_PERMANENTLY_DEFAULT"
  }
}

resource "google_compute_target_http_proxy" "http_redirect" {
  name    = "labsight-frontend-http-proxy-${var.environment}"
  project = var.project_id
  url_map = google_compute_url_map.http_redirect.id
}

resource "google_compute_global_forwarding_rule" "http_redirect" {
  name       = "labsight-frontend-http-${var.environment}"
  project    = var.project_id
  target     = google_compute_target_http_proxy.http_redirect.id
  port_range = "80"
  ip_address = google_compute_global_address.frontend.address

  load_balancing_scheme = "EXTERNAL_MANAGED"
}

# --- IAP access policy ---

resource "google_iap_web_backend_service_iam_binding" "frontend" {
  project             = var.project_id
  web_backend_service = google_compute_backend_service.frontend.name
  role                = "roles/iap.httpsResourceAccessor"
  members             = var.iap_members
}
