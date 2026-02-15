.PHONY: tf-init tf-plan tf-apply tf-destroy tf-fmt tf-validate tf-output \
       test test-ingestion test-service logs-function test-upload \
       dev-service build-service deploy-service

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

test: test-ingestion test-service

test-ingestion:
	python -m pytest ingestion/tests/ -v --cov=ingestion --cov-report=term-missing

test-service:
	cd service && python -m pytest tests/ -v

# --- Phase 2: Ingestion ---

logs-function:
	gcloud functions logs read document-ingestion-dev --region=us-east1 --gen2 --limit=20

test-upload:
	gcloud storage cp ingestion/tests/fixtures/test-doc.md gs://labsight-uploads-dev/

# --- Phase 3: RAG Service ---

dev-service:
	cd service && uvicorn app.main:create_app --factory --reload --port 8080

build-service:
	docker build -t labsight-rag-service service/

deploy-service:
	$(eval REGISTRY := $(shell cd $(TF_DIR) && terraform output -raw docker_registry_url))
	docker build -t $(REGISTRY)/rag-service:latest service/
	docker push $(REGISTRY)/rag-service:latest
	cd $(TF_DIR) && terraform apply -target=module.cloud_run_rag
