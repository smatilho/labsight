variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "uploads_bucket_name" {
  description = "Uploads GCS bucket name (for ingestion SA read access). Empty string skips the binding."
  type        = string
  default     = ""
}

variable "bigquery_dataset_id" {
  description = "BigQuery dataset ID for dataset-scoped dataEditor bindings. Empty string skips the binding."
  type        = string
  default     = ""
}

variable "bigquery_infra_dataset_id" {
  description = "Infrastructure metrics BigQuery dataset ID for dataViewer binding. Empty string skips the binding."
  type        = string
  default     = ""
}

variable "enable_gateway" {
  description = "When true, creates the API Gateway service account."
  type        = bool
  default     = false
}
