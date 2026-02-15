output "dataset_id" {
  description = "BigQuery dataset ID"
  value       = google_bigquery_dataset.platform_observability.dataset_id
}

output "ingestion_log_table_id" {
  description = "Fully-qualified ingestion_log table ID (project.dataset.table)"
  value       = "${var.project_id}.${google_bigquery_dataset.platform_observability.dataset_id}.${google_bigquery_table.ingestion_log.table_id}"
}

output "query_log_table_id" {
  description = "Fully-qualified query_log table ID (project.dataset.table)"
  value       = "${var.project_id}.${google_bigquery_dataset.platform_observability.dataset_id}.${google_bigquery_table.query_log.table_id}"
}
