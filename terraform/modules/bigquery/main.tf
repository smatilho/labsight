# BigQuery dataset for platform observability.
# Partitioned by day on timestamp for cost-efficient queries.

resource "google_bigquery_dataset" "platform_observability" {
  dataset_id  = "platform_observability_${var.environment}"
  project     = var.project_id
  location    = var.region
  description = "Labsight AI platform observability — ingestion logs, query logs, model comparisons"

  default_table_expiration_ms = 7776000000 # 90 days in ms
}

resource "google_bigquery_table" "ingestion_log" {
  dataset_id          = google_bigquery_dataset.platform_observability.dataset_id
  table_id            = "ingestion_log"
  project             = var.project_id
  deletion_protection = false
  description         = "Tracks every document ingestion: sanitization, chunking, embedding steps"

  time_partitioning {
    type  = "DAY"
    field = "timestamp"
  }

  schema = jsonencode([
    {
      name = "timestamp"
      type = "TIMESTAMP"
      mode = "REQUIRED"
    },
    {
      name = "file_name"
      type = "STRING"
      mode = "REQUIRED"
    },
    {
      name = "file_type"
      type = "STRING"
      mode = "REQUIRED"
    },
    {
      name = "file_size_bytes"
      type = "INTEGER"
      mode = "NULLABLE"
    },
    {
      name = "chunk_count"
      type = "INTEGER"
      mode = "NULLABLE"
    },
    {
      name = "chunks_sanitized"
      type = "INTEGER"
      mode = "NULLABLE"
    },
    {
      name        = "sanitization_actions"
      type        = "STRING"
      mode        = "REPEATED"
      description = "Types of sanitization applied (e.g. ip_redacted, secret_redacted)"
    },
    {
      name = "embedding_time_ms"
      type = "FLOAT"
      mode = "NULLABLE"
    },
    {
      name = "total_time_ms"
      type = "FLOAT"
      mode = "NULLABLE"
    },
    {
      name        = "status"
      type        = "STRING"
      mode        = "REQUIRED"
      description = "Processing status: success, error"
    },
    {
      name = "error_message"
      type = "STRING"
      mode = "NULLABLE"
    },
  ])
}
