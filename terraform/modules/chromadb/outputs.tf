output "service_name" {
  description = "ChromaDB Cloud Run service name"
  value       = google_cloud_run_v2_service.chromadb.name
}

output "service_url" {
  description = "ChromaDB Cloud Run service URL"
  value       = google_cloud_run_v2_service.chromadb.uri
}

output "token_secret_id" {
  description = "Secret Manager secret ID for ChromaDB auth token"
  value       = google_secret_manager_secret.chromadb_token.secret_id
}
