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
