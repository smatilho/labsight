variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "billing_account_id" {
  description = "GCP billing account ID"
  type        = string
  sensitive   = true
}

variable "owner_email" {
  description = "Email for budget notifications"
  type        = string
}

variable "budget_amount" {
  description = "Monthly budget threshold in USD"
  type        = number
}
