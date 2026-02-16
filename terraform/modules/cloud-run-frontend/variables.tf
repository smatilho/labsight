variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "region" {
  description = "Cloud Run deployment region"
  type        = string
}

variable "environment" {
  description = "Deployment environment (dev, staging, prod)"
  type        = string
}

variable "frontend_sa_email" {
  description = "Service account email for the frontend service"
  type        = string
}

variable "image" {
  description = "Docker image URI for the frontend"
  type        = string
}

variable "backend_url" {
  description = "RAG backend Cloud Run URL"
  type        = string
}
