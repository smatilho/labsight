output "uploads_bucket_name" {
  description = "GCS bucket for document uploads"
  value       = module.gcs.uploads_bucket_name
}

output "uploads_bucket_url" {
  description = "GCS bucket URL"
  value       = module.gcs.uploads_bucket_url
}

output "collector_sa_email" {
  description = "Service account for homelab metrics collector"
  value       = module.iam.collector_sa_email
}

output "ingestion_sa_email" {
  description = "Service account for Cloud Function ingestion"
  value       = module.iam.ingestion_sa_email
}

output "rag_service_sa_email" {
  description = "Service account for GKE RAG service"
  value       = module.iam.rag_service_sa_email
}

output "budget_name" {
  description = "Billing budget resource name"
  value       = module.monitoring.budget_name
}
