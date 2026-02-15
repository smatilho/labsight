# ChromaDB on Cloud Run with GCS-backed persistence.
#
# Why Cloud Run instead of a managed vector DB?
# - ChromaDB is lightweight and free (no Pinecone/Weaviate costs)
# - Cloud Run scales to zero when not in use ($0 idle cost)
# - GCS volume mount gives durable persistence without managing disks
# - For a single-user homelab project, this is the right tradeoff:
#   we get a real vector store with real persistence at near-zero cost
#
# Auth: Cloud Run IAM only. ChromaDB 1.x removed built-in token auth;
# instead, Cloud Run requires a Google ID token with roles/run.invoker.
# The token in Secret Manager is kept for potential future use but is
# not used by the ChromaDB server itself.

resource "random_password" "chromadb_token" {
  length  = 32
  special = false
}

resource "google_secret_manager_secret" "chromadb_token" {
  secret_id = "chromadb-token-${var.environment}"
  project   = var.project_id

  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "chromadb_token" {
  secret      = google_secret_manager_secret.chromadb_token.id
  secret_data = random_password.chromadb_token.result
}

# Grant the default Compute Engine SA access to the secret so Cloud Run
# can mount it as an env var. Also grant the ingestion SA.
data "google_project" "current" {
  project_id = var.project_id
}

resource "google_secret_manager_secret_iam_member" "compute_sa_access" {
  secret_id = google_secret_manager_secret.chromadb_token.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${data.google_project.current.number}-compute@developer.gserviceaccount.com"
}

resource "google_secret_manager_secret_iam_member" "ingestion_sa_access" {
  secret_id = google_secret_manager_secret.chromadb_token.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${var.ingestion_sa_email}"
}

# The ingestion SA runs the Cloud Run service and needs read/write access
# to the ChromaDB GCS bucket for the FUSE volume mount.
resource "google_storage_bucket_iam_member" "chromadb_bucket_admin" {
  bucket = var.chromadb_bucket_name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${var.ingestion_sa_email}"
}

resource "google_cloud_run_v2_service" "chromadb" {
  name                = "chromadb-${var.environment}"
  location            = var.region
  project             = var.project_id
  deletion_protection = false

  # INGRESS_TRAFFIC_ALL because Cloud Functions Gen 2 route through the
  # public internet unless a VPC connector is configured.  Cloud Run
  # returns 404 (not 403) for ingress-blocked requests — this was the
  # root cause of the /api/v2/auth/identity 404 errors.
  #
  # Security is still enforced by Cloud Run IAM: only service accounts
  # with roles/run.invoker can invoke the service.
  ingress = "INGRESS_TRAFFIC_ALL"

  template {
    execution_environment = "EXECUTION_ENVIRONMENT_GEN2"

    scaling {
      min_instance_count = 0
      max_instance_count = 2
    }

    service_account = var.ingestion_sa_email

    containers {
      # Pin to match the Python client version in ingestion/requirements.txt.
      # Client and server versions MUST match — ChromaDB doesn't guarantee
      # cross-version compatibility.
      image = "chromadb/chroma:1.5.0"

      ports {
        container_port = 8000
      }

      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
      }

      # ChromaDB 1.x hardcodes persist directory to /data. The old
      # IS_PERSISTENT and PERSIST_DIRECTORY env vars are ignored.
      # Auth env vars (CHROMA_SERVER_AUTHN_*) were also removed in 1.x;
      # Cloud Run IAM handles authentication instead.
      env {
        name  = "ANONYMIZED_TELEMETRY"
        value = "FALSE"
      }

      volume_mounts {
        name       = "chroma-data"
        mount_path = "/data"
      }
    }

    volumes {
      name = "chroma-data"
      gcs {
        bucket    = var.chromadb_bucket_name
        read_only = false
      }
    }
  }

  depends_on = [google_secret_manager_secret_version.chromadb_token]
}

# Allow the ingestion SA to invoke ChromaDB
resource "google_cloud_run_v2_service_iam_member" "ingestion_invoker" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.chromadb.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${var.ingestion_sa_email}"
}
