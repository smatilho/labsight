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

variable "rag_service_sa_email" {
  description = "Service account email for the RAG service"
  type        = string
}

variable "image" {
  description = "Docker image URI (e.g. us-east1-docker.pkg.dev/project/repo/image:tag)"
  type        = string
}

variable "chromadb_url" {
  description = "ChromaDB Cloud Run service URL"
  type        = string
}

variable "llm_provider" {
  description = "LLM provider: vertex_ai or openrouter"
  type        = string
  default     = "vertex_ai"
}

variable "openrouter_api_key" {
  description = "OpenRouter API key (only needed if llm_provider=openrouter)"
  type        = string
  default     = ""
  sensitive   = true
}

variable "bigquery_query_log_table" {
  description = "Fully-qualified BigQuery query_log table ID"
  type        = string
  default     = ""
}

variable "bigquery_metrics_dataset" {
  description = "Infrastructure metrics BigQuery dataset ID (Phase 4 agent queries)"
  type        = string
  default     = ""
}

variable "gcs_uploads_bucket" {
  description = "GCS bucket for file uploads (Phase 5)"
  type        = string
  default     = ""
}

variable "bigquery_observability_dataset" {
  description = "Observability BigQuery dataset ID for upload status and dashboard (Phase 5)"
  type        = string
  default     = ""
}

variable "frontend_sa_email" {
  description = "Frontend service account email for invoker binding (Phase 5A direct mode)"
  type        = string
  default     = ""
}

variable "gateway_sa_email" {
  description = "API Gateway service account email for invoker binding (Phase 5B)"
  type        = string
  default     = ""
}

variable "retrieval_candidate_k" {
  description = "Phase 6 candidate retrieval depth before reranking"
  type        = number
  default     = 20
}

variable "retrieval_final_k" {
  description = "Phase 6 final document count after reranking"
  type        = number
  default     = 5
}

variable "rerank_enabled" {
  description = "Enable reranking in the RAG service"
  type        = bool
  default     = false
}

variable "reranker_model" {
  description = "Cross-encoder model name used for reranking"
  type        = string
  default     = "cross-encoder/ms-marco-MiniLM-L-6-v2"
}

variable "reranker_max_candidates" {
  description = "Maximum documents scored by the reranker"
  type        = number
  default     = 30
}
