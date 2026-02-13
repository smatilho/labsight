resource "google_storage_bucket" "uploads" {
  name     = "labsight-uploads-${var.environment}"
  project  = var.project_id
  location = var.region

  uniform_bucket_level_access = true
  force_destroy               = false

  versioning {
    enabled = true
  }

  lifecycle_rule {
    condition {
      num_newer_versions = 3
    }
    action {
      type = "Delete"
    }
  }
}
