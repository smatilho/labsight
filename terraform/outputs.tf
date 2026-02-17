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

# --- Phase 3 outputs ---

output "bigquery_query_log_table" {
  description = "Fully-qualified query_log table ID"
  value       = module.bigquery.query_log_table_id
}

output "bigquery_retrieval_eval_runs_table" {
  description = "Fully-qualified retrieval_eval_runs table ID"
  value       = module.bigquery.retrieval_eval_runs_table_id
}

output "bigquery_retrieval_eval_query_results_table" {
  description = "Fully-qualified retrieval_eval_query_results table ID"
  value       = module.bigquery.retrieval_eval_query_results_table_id
}

output "rag_service_url" {
  description = "RAG service Cloud Run URL"
  value       = module.cloud_run_rag.service_url
}

output "docker_registry_url" {
  description = "Artifact Registry Docker repository URL"
  value       = module.gcs.docker_registry_url
}

# --- Phase 4 outputs ---

output "bigquery_infra_metrics_dataset" {
  description = "Infrastructure metrics BigQuery dataset ID"
  value       = module.bigquery.infra_metrics_dataset_id
}

# --- Phase 5A outputs ---

output "frontend_service_url" {
  description = "Frontend Cloud Run service URL"
  value       = module.cloud_run_frontend.service_url
}

output "frontend_sa_email" {
  description = "Frontend service account email"
  value       = module.iam.frontend_sa_email
}

# --- Phase 5B outputs ---

output "frontend_iap_url" {
  description = "IAP-protected frontend URL (empty if IAP not enabled)"
  value       = var.domain != "" ? module.iap_frontend[0].frontend_iap_url : ""
}

output "frontend_static_ip" {
  description = "Static IP for DNS A record (empty if IAP not enabled)"
  value       = var.domain != "" ? module.iap_frontend[0].static_ip : ""
}

output "iap_service_account_email" {
  description = "IAP-managed service account email used to invoke frontend Cloud Run (empty if IAP not enabled)"
  value       = var.domain != "" ? module.iap_frontend[0].iap_service_account_email : ""
}

output "api_gateway_url" {
  description = "API Gateway URL (empty if gateway not enabled)"
  value       = var.domain != "" ? module.api_gateway[0].gateway_url : ""
}

output "gateway_sa_email" {
  description = "API Gateway service account email (empty if gateway not enabled)"
  value       = module.iam.gateway_sa_email
}
