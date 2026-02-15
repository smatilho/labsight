.PHONY: tf-init tf-plan tf-apply tf-destroy tf-fmt tf-validate tf-output \
       test test-ingestion logs-function test-upload

TF_DIR = terraform

# --- Terraform ---

tf-init:
	cd $(TF_DIR) && terraform init

tf-plan:
	cd $(TF_DIR) && terraform plan

tf-apply:
	cd $(TF_DIR) && terraform apply

tf-destroy:
	cd $(TF_DIR) && terraform destroy

tf-fmt:
	cd $(TF_DIR) && terraform fmt -recursive

tf-validate:
	cd $(TF_DIR) && terraform validate

tf-output:
	cd $(TF_DIR) && terraform output

# --- Testing ---

test: test-ingestion

test-ingestion:
	python -m pytest ingestion/tests/ -v --cov=ingestion --cov-report=term-missing

# --- Phase 2: Ingestion ---

logs-function:
	gcloud functions logs read document-ingestion-dev --region=us-east1 --gen2 --limit=20

test-upload:
	gcloud storage cp ingestion/tests/fixtures/test-doc.md gs://labsight-uploads-dev/
