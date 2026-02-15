# API enablement — each phase adds its own list, merged into a single for_each.
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

  phase2_apis = [
    "cloudfunctions.googleapis.com",
    "cloudbuild.googleapis.com",
    "eventarc.googleapis.com",
    "run.googleapis.com",
    "aiplatform.googleapis.com",
    "artifactregistry.googleapis.com",
    "secretmanager.googleapis.com",
  ]
}

resource "google_project_service" "apis" {
  for_each = toset(concat(local.phase1_apis, local.phase2_apis))

  project = var.project_id
  service = each.value

  disable_on_destroy = false
}
