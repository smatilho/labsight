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

variable "iap_oauth_client_id" {
  description = "OAuth client ID for IAP backend service (from Google Auth Platform > Clients)."
  type        = string
  default     = ""
}

variable "iap_oauth_client_secret" {
  description = "OAuth client secret for IAP backend service."
  type        = string
  default     = ""
  sensitive   = true
}

variable "frontend_public" {
  description = "When true, frontend is publicly accessible (allUsers) in non-IAP mode. Must be false when domain is set."
  type        = bool
  default     = false
}

# --- Phase 6: Retrieval tuning ---

variable "retrieval_candidate_k" {
  description = "Number of ANN candidates retrieved from ChromaDB before reranking"
  type        = number
  default     = 20
}

variable "retrieval_final_k" {
  description = "Number of documents passed to generation after reranking"
  type        = number
  default     = 5
}

variable "rerank_enabled" {
  description = "Enable cross-encoder reranking in the RAG service"
  type        = bool
  default     = false
}

variable "reranker_model" {
  description = "Cross-encoder model identifier for reranking"
  type        = string
  default     = "cross-encoder/ms-marco-MiniLM-L-6-v2"
}

variable "reranker_max_candidates" {
  description = "Maximum candidate docs scored by the reranker"
  type        = number
  default     = 30
}
