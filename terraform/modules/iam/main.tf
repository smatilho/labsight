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

# Write ingestion logs to BigQuery (scoped to observability dataset only)
resource "google_bigquery_dataset_iam_member" "ingestion_bq_editor" {
  count      = var.bigquery_dataset_id != "" ? 1 : 0
  project    = var.project_id
  dataset_id = var.bigquery_dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${google_service_account.ingestion.email}"
}

# Run BigQuery jobs (required for inserts)
resource "google_project_iam_member" "ingestion_bq_job_user" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.ingestion.email}"
}

# --- Phase 3: RAG service account permissions ---

# Call Vertex AI for Gemini inference and embeddings (query-time)
resource "google_project_iam_member" "rag_vertex_ai" {
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.rag_service.email}"
}

# Write query logs to BigQuery (scoped to observability dataset only)
resource "google_bigquery_dataset_iam_member" "rag_bq_editor" {
  count      = var.bigquery_dataset_id != "" ? 1 : 0
  project    = var.project_id
  dataset_id = var.bigquery_dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${google_service_account.rag_service.email}"
}

# Run BigQuery jobs (required for streaming inserts and agent queries)
resource "google_project_iam_member" "rag_bq_job_user" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.rag_service.email}"
}

# --- Phase 5: Frontend service account ---

resource "google_service_account" "frontend" {
  account_id   = "labsight-frontend"
  display_name = "Labsight Frontend"
  description  = "Next.js frontend service that proxies to the RAG backend"
  project      = var.project_id
}

# RAG service needs to write uploads to GCS
resource "google_storage_bucket_iam_member" "rag_uploads_writer" {
  count  = var.uploads_bucket_name != "" ? 1 : 0
  bucket = var.uploads_bucket_name
  role   = "roles/storage.objectCreator"
  member = "serviceAccount:${google_service_account.rag_service.email}"
}

# --- Phase 5B: API Gateway service account ---

resource "google_service_account" "gateway" {
  count        = var.enable_gateway ? 1 : 0
  account_id   = "labsight-apigateway"
  display_name = "Labsight API Gateway"
  description  = "API Gateway SA — invokes RAG backend on behalf of frontend"
  project      = var.project_id
}

# --- Phase 4: Read-only access to infrastructure metrics for agent queries ---

resource "google_bigquery_dataset_iam_member" "rag_infra_metrics_viewer" {
  count      = var.bigquery_infra_dataset_id != "" ? 1 : 0
  project    = var.project_id
  dataset_id = var.bigquery_infra_dataset_id
  role       = "roles/bigquery.dataViewer"
  member     = "serviceAccount:${google_service_account.rag_service.email}"
}
