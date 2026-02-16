variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "region" {
  description = "GCP region"
  type        = string
}

variable "environment" {
  description = "Deployment environment (dev, staging, prod)"
  type        = string
}

variable "backend_url" {
  description = "RAG backend Cloud Run URL"
  type        = string
}

variable "frontend_sa_email" {
  description = "Frontend service account email (gets secret accessor for API key)"
  type        = string
}

variable "gateway_sa_email" {
  description = "API Gateway service account email (created in IAM module)"
  type        = string
}
