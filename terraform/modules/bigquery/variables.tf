variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "region" {
  description = "BigQuery dataset location"
  type        = string
}

variable "environment" {
  description = "Deployment environment (dev, staging, prod)"
  type        = string
}
