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

# --- Phase 3: RAG query observability ---

resource "google_bigquery_table" "query_log" {
  dataset_id          = google_bigquery_dataset.platform_observability.dataset_id
  table_id            = "query_log"
  project             = var.project_id
  deletion_protection = false
  description         = "Tracks every RAG query: model, latency, retrieval count, status"

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
      name        = "query"
      type        = "STRING"
      mode        = "REQUIRED"
      description = "User query text (truncated to 1000 chars)"
    },
    {
      name        = "query_mode"
      type        = "STRING"
      mode        = "REQUIRED"
      description = "rag, metrics, or hybrid"
    },
    {
      name = "model_used"
      type = "STRING"
      mode = "REQUIRED"
    },
    {
      name = "retrieval_count"
      type = "INTEGER"
      mode = "NULLABLE"
    },
    {
      name = "latency_ms"
      type = "FLOAT"
      mode = "NULLABLE"
    },
    {
      name        = "status"
      type        = "STRING"
      mode        = "REQUIRED"
      description = "success or error"
    },
    {
      name = "error_message"
      type = "STRING"
      mode = "NULLABLE"
    },
    {
      name        = "router_confidence"
      type        = "FLOAT"
      mode        = "NULLABLE"
      description = "Query router classification confidence (0.0-1.0)"
    },
  ])
}

# --- Phase 4: Infrastructure metrics dataset ---

resource "google_bigquery_dataset" "infrastructure_metrics" {
  dataset_id  = "infrastructure_metrics_${var.environment}"
  project     = var.project_id
  location    = var.region
  description = "Homelab infrastructure metrics — uptime events, resource utilization, service inventory"

  default_table_expiration_ms = 15552000000 # 180 days in ms
}

resource "google_bigquery_table" "uptime_events" {
  dataset_id          = google_bigquery_dataset.infrastructure_metrics.dataset_id
  table_id            = "uptime_events"
  project             = var.project_id
  deletion_protection = false
  description         = "Service uptime/downtime events from Uptime Kuma"

  time_partitioning {
    type  = "DAY"
    field = "checked_at"
  }

  schema = jsonencode([
    {
      name = "checked_at"
      type = "TIMESTAMP"
      mode = "REQUIRED"
    },
    {
      name = "service_name"
      type = "STRING"
      mode = "REQUIRED"
    },
    {
      name        = "status"
      type        = "STRING"
      mode        = "REQUIRED"
      description = "up or down"
    },
    {
      name = "response_time_ms"
      type = "FLOAT"
      mode = "NULLABLE"
    },
    {
      name = "status_code"
      type = "INTEGER"
      mode = "NULLABLE"
    },
    {
      name = "message"
      type = "STRING"
      mode = "NULLABLE"
    },
  ])
}

resource "google_bigquery_table" "resource_utilization" {
  dataset_id          = google_bigquery_dataset.infrastructure_metrics.dataset_id
  table_id            = "resource_utilization"
  project             = var.project_id
  deletion_protection = false
  description         = "Node resource utilization snapshots from Proxmox"

  time_partitioning {
    type  = "DAY"
    field = "collected_at"
  }

  schema = jsonencode([
    {
      name = "collected_at"
      type = "TIMESTAMP"
      mode = "REQUIRED"
    },
    {
      name = "node"
      type = "STRING"
      mode = "REQUIRED"
    },
    {
      name = "cpu_percent"
      type = "FLOAT"
      mode = "NULLABLE"
    },
    {
      name = "memory_percent"
      type = "FLOAT"
      mode = "NULLABLE"
    },
    {
      name = "storage_percent"
      type = "FLOAT"
      mode = "NULLABLE"
    },
  ])
}

resource "google_bigquery_table" "service_inventory" {
  dataset_id          = google_bigquery_dataset.infrastructure_metrics.dataset_id
  table_id            = "service_inventory"
  project             = var.project_id
  deletion_protection = false
  description         = "Current service inventory — names, hosts, ports, container types"

  schema = jsonencode([
    {
      name = "service_name"
      type = "STRING"
      mode = "REQUIRED"
    },
    {
      name = "host"
      type = "STRING"
      mode = "NULLABLE"
    },
    {
      name = "port"
      type = "INTEGER"
      mode = "NULLABLE"
    },
    {
      name        = "container_type"
      type        = "STRING"
      mode        = "NULLABLE"
      description = "lxc or docker"
    },
    {
      name = "last_seen"
      type = "TIMESTAMP"
      mode = "NULLABLE"
    },
  ])
}
