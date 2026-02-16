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
  description = "Backend URL (RAG service or API Gateway)"
  type        = string
}

variable "frontend_public" {
  description = "When true, adds allUsers invoker (Phase 5A). When false, IAP controls access."
  type        = bool
  default     = false
}

variable "backend_auth_mode" {
  description = "Backend auth mode: id_token (direct Cloud Run) or api_key (via API Gateway)"
  type        = string
  default     = "id_token"

  validation {
    condition     = contains(["id_token", "api_key"], var.backend_auth_mode)
    error_message = "backend_auth_mode must be id_token or api_key."
  }
}

variable "api_key_secret_id" {
  description = "Secret Manager secret ID for the gateway API key (only used when backend_auth_mode=api_key)"
  type        = string
  default     = ""
}
