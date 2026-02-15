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

# --- Phase 2 outputs ---

output "chromadb_service_url" {
  description = "ChromaDB Cloud Run service URL"
  value       = module.chromadb.service_url
}

output "ingestion_function_name" {
  description = "Document ingestion Cloud Function name"
  value       = module.cloud_functions.function_name
}

output "bigquery_dataset_id" {
  description = "Platform observability BigQuery dataset ID"
  value       = module.bigquery.dataset_id
}

output "bigquery_ingestion_table" {
  description = "Fully-qualified ingestion_log table ID"
  value       = module.bigquery.ingestion_log_table_id
}
