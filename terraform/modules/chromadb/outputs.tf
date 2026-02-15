output "service_name" {
  description = "ChromaDB Cloud Run service name"
  value       = google_cloud_run_v2_service.chromadb.name
}

output "service_url" {
  description = "ChromaDB Cloud Run service URL"
  value       = google_cloud_run_v2_service.chromadb.uri
}