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

variable "domain" {
  description = "Domain for the managed SSL certificate (e.g. labsight.atilho.com)"
  type        = string
}

variable "frontend_service_name" {
  description = "Cloud Run service name for the frontend"
  type        = string
}

variable "iap_members" {
  description = "List of IAP-allowed members (e.g. [\"user:you@gmail.com\"])"
  type        = list(string)
}
