.PHONY: tf-init tf-plan tf-apply tf-destroy tf-fmt tf-validate tf-output \
       test test-ingestion test-service test-frontend \
       dev-service build-service deploy-service \
       dev-frontend install-frontend build-frontend deploy-frontend \
       logs-function test-upload \
       seed-metrics test-router-accuracy \
       eval-retrieval benchmark-retrieval benchmark-hnsw

PYTHON ?= python3
TF_DIR = terraform
DOCKER_PLATFORM ?= linux/amd64
TF_AUTO_APPROVE ?= false
TF_APPLY_FLAGS =
ifeq ($(TF_AUTO_APPROVE),true)
TF_APPLY_FLAGS += -auto-approve
endif

# --- Terraform ---

tf-init:
	cd $(TF_DIR) && terraform init

tf-plan:
	cd $(TF_DIR) && terraform plan

tf-apply:
	cd $(TF_DIR) && terraform apply $(TF_APPLY_FLAGS)

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
	@if $(PYTHON) -c "import importlib.util,sys; sys.exit(0 if importlib.util.find_spec('pytest_cov') else 1)"; then \
		$(PYTHON) -m pytest ingestion/tests/ -v --cov=ingestion --cov-report=term-missing; \
	else \
		echo "pytest-cov not installed; running ingestion tests without coverage."; \
		$(PYTHON) -m pytest ingestion/tests/ -v; \
	fi

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
	docker buildx build --platform $(DOCKER_PLATFORM) -t $(REGISTRY)/rag-service:latest service --push
	cd $(TF_DIR) && terraform apply $(TF_APPLY_FLAGS) -target=module.cloud_run_rag

# --- Phase 4: Agent + BigQuery ---

seed-metrics:
	$(PYTHON) scripts/seed_metrics.py --project-id labsight-487303 --dataset infrastructure_metrics_dev

test-router-accuracy:
	$(PYTHON) scripts/test_router_accuracy.py

# --- Phase 6: Retrieval tuning ---

eval-retrieval:
	PYTHONPATH=service $(PYTHON) scripts/eval_retrieval.py \
		--bq-project labsight-487303 \
		--bq-dataset platform_observability_dev \
		--no-threshold-gate

benchmark-retrieval:
	PYTHONPATH=service $(PYTHON) scripts/benchmark_retrieval.py --no-threshold-gate

benchmark-hnsw:
	PYTHONPATH=service $(PYTHON) scripts/benchmark_hnsw.py

# --- Phase 5: Frontend ---

install-frontend:
	cd frontend && npm ci

dev-frontend:
	cd frontend && npm run dev

build-frontend:
	docker build -t labsight-frontend frontend/

deploy-frontend:
	$(eval REGISTRY := $(shell cd $(TF_DIR) && terraform output -raw docker_registry_url))
	docker buildx build --platform $(DOCKER_PLATFORM) -t $(REGISTRY)/frontend:latest frontend --push
	cd $(TF_DIR) && terraform apply $(TF_APPLY_FLAGS) -target=module.cloud_run_frontend
