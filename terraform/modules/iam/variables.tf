variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "uploads_bucket_name" {
  description = "Uploads GCS bucket name (for ingestion SA read access). Empty string skips the binding."
  type        = string
  default     = ""
}
