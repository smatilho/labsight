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

# --- Phase 2: Ingestion service account permissions ---

# Read uploaded documents from the uploads bucket
resource "google_storage_bucket_iam_member" "ingestion_uploads_reader" {
  count  = var.uploads_bucket_name != "" ? 1 : 0
  bucket = var.uploads_bucket_name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${google_service_account.ingestion.email}"
}

# Call Vertex AI embedding endpoints
resource "google_project_iam_member" "ingestion_vertex_ai" {
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.ingestion.email}"
}

# Write ingestion logs to BigQuery
resource "google_project_iam_member" "ingestion_bq_editor" {
  project = var.project_id
  role    = "roles/bigquery.dataEditor"
  member  = "serviceAccount:${google_service_account.ingestion.email}"
}

# Run BigQuery jobs (required for inserts)
resource "google_project_iam_member" "ingestion_bq_job_user" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.ingestion.email}"
}

# Read ChromaDB auth token from Secret Manager
resource "google_project_iam_member" "ingestion_secret_accessor" {
  project = var.project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${google_service_account.ingestion.email}"
}
