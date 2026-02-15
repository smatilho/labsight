# Labsight

AI-powered operations assistant for self-hosted infrastructure. Ingests real homelab documentation and infrastructure metrics, then uses RAG and agentic tool use to answer questions about your environment.

## What Is This?

Labsight is an AIOps platform built on GCP that combines document retrieval (RAG) with metrics analysis. Upload your homelab docs — markdown runbooks, docker-compose files, config files — and Labsight sanitizes sensitive data, chunks intelligently by file type, embeds with Vertex AI, and stores vectors in ChromaDB for retrieval. Ask a question and get a cited answer powered by Gemini or Claude, with every query logged to BigQuery for observability. All infrastructure is Terraform-managed.

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
                    │  (Cloud Run,     │◄──────┐       │  ingestion_log  │
                    │   GCS-backed)    │       │       │  query_log      │
                    └──────────────────┘       │       │  (observability)│
                                               │       └────────┬────────┘
                                               │                │
                                    ┌──────────┴────────────────┘
                                    │
                         ┌──────────┴──────────┐
                         │  Cloud Run          │
                         │  (RAG Service)      │
                         │  FastAPI + LangChain│
                         │                     │
                         │  ├─ Retriever       │
                         │  ├─ RAG Chain       │
                         │  ├─ Input Validator │
                         │  └─ Query Logger    │
                         └──────────┬──────────┘
                                    │
                         ┌──────────┴──────────┐
                         │  LLM Provider       │
                         │  (model-agnostic)   │
                         │                     │
                         │  Vertex AI (Gemini) │
                         │  OR                 │
                         │  OpenRouter (Claude) │
                         └─────────────────────┘
```

## Tech Stack

| Layer | Technology |
|---|---|
| Infrastructure | Terraform (HCL), GCP |
| RAG Service | FastAPI, LangChain, Cloud Run (Python 3.12) |
| Document Ingestion | Cloud Functions Gen 2 (Python 3.12) |
| Data Sanitization | Regex-based IP/secret redaction |
| Chunking | File-type-aware (markdown, YAML, config, fallback) |
| Embeddings | Vertex AI text-embedding-004 |
| LLM (Primary) | Gemini 2.0 Flash via Vertex AI |
| LLM (Secondary) | Claude via OpenRouter (model-agnostic swap) |
| Vector Store | ChromaDB on Cloud Run (GCS persistence) |
| Observability | BigQuery (platform_observability dataset) |
| Auth | Cloud Run IAM (ID token), IAM service accounts |
| Secrets | GCP Secret Manager (OpenRouter API key) |
| Container Registry | Artifact Registry |
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
├── service/                       # RAG service (Cloud Run)
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── app/
│   │   ├── main.py                # FastAPI app factory (lifespan)
│   │   ├── config.py              # Pydantic settings (LABSIGHT_ prefix)
│   │   ├── routers/
│   │   │   ├── chat.py            # /api/chat (streaming + non-streaming)
│   │   │   └── health.py          # /api/health
│   │   ├── rag/
│   │   │   ├── retriever.py       # ChromaDB retriever (LangChain BaseRetriever)
│   │   │   └── chain.py           # RAG chain with [Source N] citations
│   │   ├── llm/
│   │   │   ├── provider.py        # Model-agnostic interface + factory
│   │   │   ├── vertex_ai.py       # Gemini via Vertex AI
│   │   │   └── openrouter.py      # Claude via OpenRouter
│   │   ├── guardrails/
│   │   │   └── input_validator.py # Prompt injection detection, length limits
│   │   └── observability/
│   │       └── logger.py          # BigQuery query logging
│   └── tests/
│       ├── conftest.py
│       ├── test_chain.py
│       ├── test_chat.py
│       ├── test_health.py
│       ├── test_input_validator.py
│       ├── test_llm_providers.py
│       └── test_retriever.py
│
├── terraform/                     # All GCP infrastructure
│   ├── main.tf                    # Provider config, module wiring
│   ├── apis.tf                    # API enablement
│   ├── variables.tf
│   ├── outputs.tf
│   └── modules/
│       ├── gcs/                   # Storage buckets + Artifact Registry
│       ├── iam/                   # Service accounts + bindings
│       ├── monitoring/            # Billing budget alerts
│       ├── bigquery/              # Observability dataset (ingestion_log, query_log)
│       ├── chromadb/              # ChromaDB Cloud Run service
│       ├── cloud-functions/       # Ingestion function
│       └── cloud-run-rag/         # RAG service (Cloud Run + Secret Manager)
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
pip install -r service/requirements.txt pytest pytest-asyncio
make test

# Upload a test document (after infra is deployed)
make test-upload

# Build and deploy the RAG service
make build-service
make deploy-service

# Check logs
make logs-function
```

## Roadmap

- [x] **Phase 1:** GCP foundation — Terraform, GCS, IAM, billing budget
- [x] **Phase 2:** Document ingestion pipeline — sanitizer, chunker, embedder, Cloud Function
- [x] **Phase 3:** Core RAG service — FastAPI, model abstraction, retrieval chain, citations, streaming
- [ ] **Phase 4:** Agent + BigQuery — LangGraph agent, metrics collector, SQL tool
- [ ] **Phase 5:** Frontend — Next.js chat UI, upload interface, dashboard
- [ ] **Phase 6:** RAG tuning — cross-encoder re-ranking, HNSW benchmarking
- [ ] **Phase 7:** Guardrails, ADK evaluation, CI/CD, polish

See [CHANGELOG.md](CHANGELOG.md) for detailed version history.

## Cost

Runs almost entirely within GCP free tier. Vertex AI embedding calls are fractions of a cent. Gemini 2.0 Flash has a generous free tier. Cloud Run scales to zero when idle. Billing alert set at $25/month as a safety net.
