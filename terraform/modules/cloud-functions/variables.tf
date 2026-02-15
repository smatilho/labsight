variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "region" {
  description = "Cloud Functions deployment region"
  type        = string
}

variable "environment" {
  description = "Deployment environment (dev, staging, prod)"
  type        = string
}

variable "uploads_bucket_name" {
  description = "GCS bucket that triggers ingestion on file upload"
  type        = string
}

variable "artifacts_bucket_name" {
  description = "GCS bucket for Cloud Function source code archives"
  type        = string
}

variable "ingestion_sa_email" {
  description = "Service account email for the Cloud Function"
  type        = string
}

variable "chromadb_url" {
  description = "ChromaDB Cloud Run service URL"
  type        = string
}

variable "bigquery_table_id" {
  description = "Fully-qualified BigQuery ingestion_log table ID"
  type        = string
}
