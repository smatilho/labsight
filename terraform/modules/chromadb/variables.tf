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

variable "chromadb_bucket_name" {
  description = "GCS bucket for ChromaDB persistent storage"
  type        = string
}

variable "ingestion_sa_email" {
  description = "Ingestion service account email (granted invoker access)"
  type        = string
}

variable "rag_service_sa_email" {
  description = "RAG service account email (granted invoker access)"
  type        = string
  default     = ""
}
