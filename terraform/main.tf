terraform {
  required_version = ">= 1.5"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
    google-beta = {
      source  = "hashicorp/google-beta"
      version = "~> 6.0"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.0"
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

provider "google-beta" {
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

locals {
  iap_enabled = var.domain != ""
}

check "iap_requires_non_public_frontend" {
  assert {
    condition     = !(local.iap_enabled && var.frontend_public)
    error_message = "frontend_public must be false when domain is set (IAP mode). Set TF_VAR_frontend_public=false or clear TF_VAR_domain."
  }
}

check "iap_requires_members" {
  assert {
    condition     = !local.iap_enabled || length(var.iap_members) > 0
    error_message = "When domain is set (IAP mode), set TF_VAR_iap_members with at least one principal (e.g. [\"user:you@example.com\"])."
  }
}

check "iap_requires_oauth_client" {
  assert {
    condition = !local.iap_enabled || (
      trimspace(var.iap_oauth_client_id) != "" &&
      trimspace(var.iap_oauth_client_secret) != ""
    )
    error_message = "When domain is set (IAP mode), set both TF_VAR_iap_oauth_client_id and TF_VAR_iap_oauth_client_secret."
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

  project_id                = var.project_id
  uploads_bucket_name       = module.gcs.uploads_bucket_name
  bigquery_dataset_id       = module.bigquery.dataset_id
  bigquery_infra_dataset_id = module.bigquery.infra_metrics_dataset_id
  enable_gateway            = local.iap_enabled

  depends_on = [google_project_service.apis, module.bigquery]
}

module "monitoring" {
  source = "./modules/monitoring"

  project_id         = var.project_id
  billing_account_id = var.billing_account_id
  owner_email        = var.owner_email
  budget_amount      = var.budget_amount

  depends_on = [google_project_service.apis]
}

# --- Phase 2: Document ingestion pipeline ---

module "bigquery" {
  source = "./modules/bigquery"

  project_id  = var.project_id
  region      = var.region
  environment = var.environment

  depends_on = [google_project_service.apis]
}

module "chromadb" {
  source = "./modules/chromadb"

  project_id           = var.project_id
  region               = var.region
  environment          = var.environment
  chromadb_bucket_name = module.gcs.chromadb_bucket_name
  ingestion_sa_email   = module.iam.ingestion_sa_email
  rag_service_sa_email = module.iam.rag_service_sa_email

  depends_on = [google_project_service.apis, module.gcs]
}

module "cloud_functions" {
  source = "./modules/cloud-functions"

  project_id            = var.project_id
  region                = var.region
  environment           = var.environment
  uploads_bucket_name   = module.gcs.uploads_bucket_name
  artifacts_bucket_name = module.gcs.function_artifacts_bucket_name
  ingestion_sa_email    = module.iam.ingestion_sa_email
  chromadb_url          = module.chromadb.service_url
  bigquery_table_id     = module.bigquery.ingestion_log_table_id

  depends_on = [module.chromadb, module.bigquery, module.iam]
}

# --- Phase 3: Core RAG service ---

module "cloud_run_rag" {
  source = "./modules/cloud-run-rag"

  project_id                     = var.project_id
  region                         = var.region
  environment                    = var.environment
  rag_service_sa_email           = module.iam.rag_service_sa_email
  image                          = "${module.gcs.docker_registry_url}/rag-service:latest"
  chromadb_url                   = module.chromadb.service_url
  bigquery_query_log_table       = module.bigquery.query_log_table_id
  bigquery_metrics_dataset       = module.bigquery.infra_metrics_dataset_id
  gcs_uploads_bucket             = module.gcs.uploads_bucket_name
  bigquery_observability_dataset = module.bigquery.dataset_id
  frontend_sa_email              = module.iam.frontend_sa_email
  gateway_sa_email               = module.iam.gateway_sa_email

  depends_on = [module.chromadb, module.bigquery, module.iam, module.gcs]
}

# --- Phase 5A: Frontend ---

module "cloud_run_frontend" {
  source = "./modules/cloud-run-frontend"

  project_id        = var.project_id
  region            = var.region
  environment       = var.environment
  frontend_sa_email = module.iam.frontend_sa_email
  image             = "${module.gcs.docker_registry_url}/frontend:latest"
  frontend_public   = local.iap_enabled ? false : var.frontend_public

  # When API Gateway is enabled (domain set), route through gateway with API key auth.
  # Otherwise, direct Cloud Run with ID token auth (Phase 5A fallback).
  backend_url       = local.iap_enabled ? "https://${module.api_gateway[0].gateway_url}" : module.cloud_run_rag.service_url
  backend_auth_mode = local.iap_enabled ? "api_key" : "id_token"
  api_key_secret_id = local.iap_enabled ? module.api_gateway[0].api_key_secret_id : ""

  depends_on = [module.cloud_run_rag, module.iam, module.gcs, module.api_gateway]
}

# --- Phase 5B: IAP + API Gateway ---

module "iap_frontend" {
  source = "./modules/iap-frontend"
  count  = local.iap_enabled ? 1 : 0

  project_id              = var.project_id
  region                  = var.region
  environment             = var.environment
  domain                  = var.domain
  frontend_service_name   = module.cloud_run_frontend.service_name
  iap_members             = var.iap_members
  iap_oauth_client_id     = var.iap_oauth_client_id
  iap_oauth_client_secret = var.iap_oauth_client_secret

  depends_on = [module.cloud_run_frontend, google_project_service.apis]
}

module "api_gateway" {
  source = "./modules/api-gateway"
  count  = local.iap_enabled ? 1 : 0

  project_id        = var.project_id
  region            = var.region
  environment       = var.environment
  backend_url       = module.cloud_run_rag.service_url
  frontend_sa_email = module.iam.frontend_sa_email
  gateway_sa_email  = module.iam.gateway_sa_email

  depends_on = [module.cloud_run_rag, module.iam, google_project_service.apis]
}
