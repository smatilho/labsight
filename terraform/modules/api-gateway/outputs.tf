output "gateway_url" {
  description = "API Gateway default hostname"
  value       = google_api_gateway_gateway.labsight.default_hostname
}

output "gateway_sa_email" {
  description = "API Gateway service account email (pass-through from IAM module)"
  value       = var.gateway_sa_email
}

output "api_key_secret_id" {
  description = "Secret Manager secret ID for the gateway API key"
  value       = google_secret_manager_secret.api_key.secret_id
}
