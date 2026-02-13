terraform {
  required_version = ">= 1.5"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
  zone    = var.zone

  user_project_override = true
  billing_project       = var.project_id

  default_labels = {
    project     = "labsight"
    environment = var.environment
    managed_by  = "terraform"
  }
}

module "gcs" {
  source = "./modules/gcs"

  project_id  = var.project_id
  region      = var.region
  environment = var.environment

  depends_on = [google_project_service.apis]
}

module "iam" {
  source = "./modules/iam"

  project_id = var.project_id

  depends_on = [google_project_service.apis]
}

module "monitoring" {
  source = "./modules/monitoring"

  project_id         = var.project_id
  billing_account_id = var.billing_account_id
  owner_email        = var.owner_email
  budget_amount      = var.budget_amount

  depends_on = [google_project_service.apis]
}
