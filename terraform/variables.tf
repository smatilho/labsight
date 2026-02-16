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
  default     = 50
}

# --- Phase 5B: IAP + API Gateway ---

variable "domain" {
  description = "Domain for the IAP-protected frontend (e.g. labsight.atilho.com)"
  type        = string
  default     = ""
}

variable "iap_members" {
  description = "List of IAP-allowed members (e.g. [\"user:you@gmail.com\"])"
  type        = list(string)
  default     = []
}

variable "frontend_public" {
  description = "When true, frontend is publicly accessible (allUsers) in non-IAP mode. Must be false when domain is set."
  type        = bool
  default     = false
}
