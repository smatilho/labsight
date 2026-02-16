.PHONY: tf-init tf-plan tf-apply tf-destroy tf-fmt tf-validate tf-output \
       test test-ingestion test-service test-frontend \
       dev-service build-service deploy-service \
       dev-frontend install-frontend build-frontend deploy-frontend \
       logs-function test-upload \
       seed-metrics test-router-accuracy

PYTHON ?= python3
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

test: test-ingestion test-service test-frontend

test-ingestion:
	$(PYTHON) -m pytest ingestion/tests/ -v --cov=ingestion --cov-report=term-missing

test-service:
	PYTHONPATH=service $(PYTHON) -m pytest service/tests/ -v

test-frontend:
	cd frontend && npm test

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

# --- Phase 4: Agent + BigQuery ---

seed-metrics:
	$(PYTHON) scripts/seed_metrics.py --project-id labsight-487303 --dataset infrastructure_metrics_dev

test-router-accuracy:
	$(PYTHON) scripts/test_router_accuracy.py

# --- Phase 5: Frontend ---

install-frontend:
	cd frontend && npm ci

dev-frontend:
	cd frontend && npm run dev

build-frontend:
	docker build -t labsight-frontend frontend/

deploy-frontend:
	$(eval REGISTRY := $(shell cd $(TF_DIR) && terraform output -raw docker_registry_url))
	docker build -t $(REGISTRY)/frontend:latest frontend/
	docker push $(REGISTRY)/frontend:latest
	cd $(TF_DIR) && terraform apply -target=module.cloud_run_frontend
