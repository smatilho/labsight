output "collector_sa_email" {
  description = "Collector service account email"
  value       = google_service_account.collector.email
}

output "ingestion_sa_email" {
  description = "Ingestion service account email"
  value       = google_service_account.ingestion.email
}

output "rag_service_sa_email" {
  description = "RAG service account email"
  value       = google_service_account.rag_service.email
}

output "frontend_sa_email" {
  description = "Frontend service account email"
  value       = google_service_account.frontend.email
}
