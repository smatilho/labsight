terraform {
  required_version = ">= 1.5"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.0"
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

module "gcs" {
  source = "./modules/gcs"

  project_id  = var.project_id
  region      = var.region
  environment = var.environment

  depends_on = [google_project_service.apis]
}

module "iam" {
  source = "./modules/iam"

  project_id          = var.project_id
  uploads_bucket_name = module.gcs.uploads_bucket_name
  bigquery_dataset_id = module.bigquery.dataset_id

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

  project_id               = var.project_id
  region                   = var.region
  environment              = var.environment
  rag_service_sa_email     = module.iam.rag_service_sa_email
  image                    = "${module.gcs.docker_registry_url}/rag-service:latest"
  chromadb_url             = module.chromadb.service_url
  bigquery_query_log_table = module.bigquery.query_log_table_id

  depends_on = [module.chromadb, module.bigquery, module.iam, module.gcs]
}
