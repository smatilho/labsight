# Service accounts with zero permissions — least privilege.
# Each phase adds only the IAM bindings its service account needs.

resource "google_service_account" "collector" {
  account_id   = "labsight-collector"
  display_name = "Labsight Metrics Collector"
  description  = "Homelab-side collector that pushes metrics to GCS/BigQuery"
  project      = var.project_id
}

resource "google_service_account" "ingestion" {
  account_id   = "labsight-ingestion"
  display_name = "Labsight Document Ingestion"
  description  = "Cloud Function for document processing and embedding"
  project      = var.project_id
}

resource "google_service_account" "rag_service" {
  account_id   = "labsight-rag-service"
  display_name = "Labsight RAG Service"
  description  = "GKE service for RAG retrieval and agent queries"
  project      = var.project_id
}
