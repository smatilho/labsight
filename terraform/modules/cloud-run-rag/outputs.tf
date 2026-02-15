output "service_name" {
  description = "RAG service Cloud Run service name"
  value       = google_cloud_run_v2_service.rag_service.name
}

output "service_url" {
  description = "RAG service Cloud Run URL"
  value       = google_cloud_run_v2_service.rag_service.uri
}
