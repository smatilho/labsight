# Cloud Function Gen 2 for document ingestion.
#
# Triggered by GCS object creation in the uploads bucket. Downloads the
# file, runs it through sanitization → chunking → embedding → ChromaDB,
# then logs the result to BigQuery.
#
# The archive_file data source zips the ingestion/ directory. The MD5 hash
# in the object name forces a redeploy whenever the code changes.

data "archive_file" "ingestion_source" {
  type        = "zip"
  source_dir  = "${path.module}/../../../ingestion"
  output_path = "${path.module}/../../../.build/ingestion-source.zip"
  excludes    = ["tests", "tests/**", "__pycache__", "**/__pycache__", ".pytest_cache", "**/.pytest_cache"]
}

resource "google_storage_bucket_object" "ingestion_source" {
  name   = "ingestion-source-${data.archive_file.ingestion_source.output_md5}.zip"
  bucket = var.artifacts_bucket_name
  source = data.archive_file.ingestion_source.output_path
}

# EventArc requires a dedicated service account for GCS triggers on
# Cloud Functions Gen 2. This SA needs pubsub and eventarc permissions.
resource "google_service_account" "eventarc" {
  account_id   = "labsight-eventarc"
  display_name = "Labsight EventArc Trigger"
  description  = "Receives GCS events and triggers the ingestion Cloud Function"
  project      = var.project_id
}

resource "google_project_iam_member" "eventarc_event_receiver" {
  project = var.project_id
  role    = "roles/eventarc.eventReceiver"
  member  = "serviceAccount:${google_service_account.eventarc.email}"
}

resource "google_project_iam_member" "eventarc_invoker" {
  project = var.project_id
  role    = "roles/run.invoker"
  member  = "serviceAccount:${google_service_account.eventarc.email}"
}

# GCS needs pubsub.publisher to send notifications to the EventArc topic.
# Without this, the GCS → EventArc → Cloud Function trigger chain fails.
data "google_storage_project_service_account" "gcs_account" {
  project = var.project_id
}

resource "google_project_iam_member" "gcs_pubsub_publisher" {
  project = var.project_id
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:${data.google_storage_project_service_account.gcs_account.email_address}"
}

resource "google_cloudfunctions2_function" "document_ingestion" {
  name     = "document-ingestion-${var.environment}"
  location = var.region
  project  = var.project_id

  build_config {
    runtime     = "python312"
    entry_point = "process_document"

    source {
      storage_source {
        bucket = var.artifacts_bucket_name
        object = google_storage_bucket_object.ingestion_source.name
      }
    }
  }

  service_config {
    max_instance_count    = 10
    min_instance_count    = 0
    available_memory      = "1Gi"
    available_cpu         = "1"
    timeout_seconds       = 540
    service_account_email = var.ingestion_sa_email

    environment_variables = {
      CHROMADB_URL   = var.chromadb_url
      BIGQUERY_TABLE = var.bigquery_table_id
      ENVIRONMENT    = var.environment
      GCP_PROJECT    = var.project_id
      GCP_LOCATION   = var.region
    }
  }

  event_trigger {
    trigger_region        = var.region
    event_type            = "google.cloud.storage.object.v1.finalized"
    retry_policy          = "RETRY_POLICY_RETRY"
    service_account_email = google_service_account.eventarc.email

    event_filters {
      attribute = "bucket"
      value     = var.uploads_bucket_name
    }
  }
}
