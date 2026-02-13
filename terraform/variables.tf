variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "region" {
  description = "GCP region for resource deployment"
  type        = string
  default     = "us-east1"
}

variable "zone" {
  description = "GCP zone for zonal resources"
  type        = string
  default     = "us-east1-b"
}

variable "environment" {
  description = "Deployment environment"
  type        = string
  default     = "dev"

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Environment must be dev, staging, or prod."
  }
}

variable "billing_account_id" {
  description = "GCP billing account ID for budget alerts"
  type        = string
  sensitive   = true
}

variable "owner_email" {
  description = "Email for billing and monitoring notifications"
  type        = string
}

variable "budget_amount" {
  description = "Monthly budget alert threshold in USD"
  type        = number
  default     = 25
}
