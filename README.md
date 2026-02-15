# Labsight

AI-powered operations assistant for self-hosted infrastructure. Ingests real homelab documentation and infrastructure metrics, then uses RAG and agentic tool use to answer questions about your environment.

## What Is This?

Labsight is an AIOps platform built on GCP that combines document retrieval (RAG) with metrics analysis. Upload your homelab docs — markdown runbooks, docker-compose files, config files — and Labsight sanitizes sensitive data, chunks intelligently by file type, embeds with Vertex AI, and stores vectors in ChromaDB for retrieval. All infrastructure is Terraform-managed.

## Architecture

```
                         ┌─────────────────────┐
                         │   GCS Uploads Bucket │
                         │  (labsight-uploads)  │
                         └──────────┬───────────┘
                                    │ object.finalized
                                    ▼
                         ┌─────────────────────┐
                         │   Cloud Function     │
                         │  (document-ingestion)│
                         └──────────┬───────────┘
                                    │
                    ┌───────────────┼───────────────┐
                    ▼               ▼               ▼
             ┌────────────┐ ┌────────────┐ ┌──────────────┐
             │ Sanitizer  │ │  Chunker   │ │   Embedder   │
             │ Strip IPs, │ │ MD/YAML/   │ │  Vertex AI   │
             │ secrets    │ │ config/    │ │  text-embed  │
             │            │ │ fallback   │ │  -004        │
             └────────────┘ └────────────┘ └──────┬───────┘
                                                   │
                              ┌────────────────────┼──────────────┐
                              ▼                                   ▼
                    ┌──────────────────┐               ┌─────────────────┐
                    │    ChromaDB      │               │    BigQuery     │
                    │  (Cloud Run,     │               │  ingestion_log  │
                    │   GCS-backed)    │               │  (observability)│
                    └──────────────────┘               └─────────────────┘
```

## Tech Stack

| Layer | Technology |
|---|---|
| Infrastructure | Terraform (HCL), GCP |
| Document Ingestion | Cloud Functions Gen 2 (Python 3.12) |
| Data Sanitization | Regex-based IP/secret redaction |
| Chunking | File-type-aware (markdown, YAML, config, fallback) |
| Embeddings | Vertex AI text-embedding-004 |
| Vector Store | ChromaDB on Cloud Run (GCS persistence) |
| Observability | BigQuery (platform_observability dataset) |
| Auth | Cloud Run IAM (ID token), IAM service accounts |
| Event Triggers | EventArc (GCS → Cloud Function) |

## Project Structure

```
labsight/
├── ingestion/                     # Document ingestion pipeline
│   ├── main.py                    # Cloud Function entry point
│   ├── sanitizer.py               # IP/secret redaction
│   ├── chunker.py                 # File-type-aware chunking
│   ├── embedder.py                # Vertex AI embeddings
│   ├── requirements.txt
│   └── tests/
│       ├── test_sanitizer.py
│       ├── test_chunker.py
│       ├── test_embedder.py
│       └── fixtures/
│
├── terraform/                     # All GCP infrastructure
│   ├── main.tf                    # Provider config, module wiring
│   ├── apis.tf                    # API enablement (Phase 1 + 2)
│   ├── variables.tf
│   ├── outputs.tf
│   └── modules/
│       ├── gcs/                   # Storage buckets
│       ├── iam/                   # Service accounts + bindings
│       ├── monitoring/            # Billing budget alerts
│       ├── bigquery/              # Observability dataset
│       ├── chromadb/              # ChromaDB Cloud Run service
│       └── cloud-functions/       # Ingestion function
│
├── Makefile
├── CHANGELOG.md
└── .env.example
```

## Prerequisites

- GCP project with billing enabled
- [Terraform](https://developer.hashicorp.com/terraform/install) >= 1.5
- Python 3.12+
- [gcloud CLI](https://cloud.google.com/sdk/docs/install) authenticated (`gcloud auth application-default login`)

## Getting Started

```bash
# Clone
git clone https://github.com/smatilho/labsight.git
cd labsight

# Deploy infrastructure
cp terraform/terraform.tfvars.example terraform/terraform.tfvars
# Edit terraform.tfvars with your project ID, billing account, email
cd terraform
terraform init
terraform plan    # Review what will be created
terraform apply   # Deploy (requires approval)

# Run tests
cd ..
python -m venv .venv && source .venv/bin/activate
pip install pyyaml pytest pytest-cov pytest-mock google-cloud-aiplatform
make test-ingestion

# Upload a test document (after infra is deployed)
make test-upload

# Check ingestion logs
make logs-function
```

## Roadmap

- [x] **Phase 1:** GCP foundation — Terraform, GCS, IAM, billing budget
- [x] **Phase 2:** Document ingestion pipeline — sanitizer, chunker, embedder, Cloud Function
- [ ] **Phase 3:** Core RAG service — FastAPI, model abstraction, retrieval chain
- [ ] **Phase 4:** Agent + BigQuery — LangGraph agent, metrics collector, SQL tool
- [ ] **Phase 5:** Frontend — Next.js chat UI, upload interface, dashboard
- [ ] **Phase 6:** RAG tuning — cross-encoder re-ranking, HNSW benchmarking
- [ ] **Phase 7:** Guardrails, ADK evaluation, CI/CD, polish

See [CHANGELOG.md](CHANGELOG.md) for detailed version history.

## Cost

Runs almost entirely within GCP free tier. Vertex AI embedding calls are fractions of a cent. Billing alert set at $25/month as a safety net. ChromaDB on Cloud Run scales to zero when idle.
