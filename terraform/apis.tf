# Phase 1 APIs — later phases add their own via this same pattern.
# disable_on_destroy = false prevents `terraform destroy` from disabling
# APIs that other resources (or the GCP console) depend on.

locals {
  phase1_apis = [
    "cloudresourcemanager.googleapis.com",
    "iam.googleapis.com",
    "storage.googleapis.com",
    "billingbudgets.googleapis.com",
    "monitoring.googleapis.com",
    "logging.googleapis.com",
    "bigquery.googleapis.com",
    "serviceusage.googleapis.com",
  ]
}

resource "google_project_service" "apis" {
  for_each = toset(local.phase1_apis)

  project = var.project_id
  service = each.value

  disable_on_destroy = false
}
