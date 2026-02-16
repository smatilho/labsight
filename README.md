# Labsight

AI-powered operations assistant for self-hosted infrastructure. Ingests real homelab documentation and infrastructure metrics, then uses RAG and tool-using agents to answer questions about your environment.

## What Is This?

Labsight is an AIOps platform built on GCP that combines document retrieval (RAG) with metrics analysis via a tool-using agent. Upload your homelab docs — markdown runbooks, docker-compose files, config files — and Labsight sanitizes sensitive data, chunks intelligently by file type, embeds with Vertex AI, and stores vectors in ChromaDB for retrieval. A heuristic router classifies queries as documentation, metrics, or hybrid — documentation queries use a RAG chain with citations, while metrics and hybrid queries are dispatched to a LangGraph ReAct agent with tools for BigQuery SQL execution and vector retrieval. Every query is logged to BigQuery with router confidence scores for observability. A Next.js frontend provides a streaming chat interface, file upload with ingestion status, and a dashboard with live BigQuery-backed metrics. All infrastructure is Terraform-managed.

## Architecture

```
Browser (public)
    │
    ▼
┌──────────────────────┐
│  Cloud Run           │
│  (Next.js Frontend)  │──── server-side proxy (ID token auth) ───┐
│  /chat, /upload,     │                                           │
│  /dashboard          │                                           │
└──────────────────────┘                                           │
                                                                   ▼
                         ┌─────────────────────┐        ┌──────────────────────┐
                         │   GCS Uploads Bucket │        │  Cloud Run           │
                         │  (labsight-uploads)  │◄───────│  (RAG Service)       │
                         └──────────┬───────────┘  file  │  FastAPI + LangGraph │
                                    │ object.       upload│                     │
                                    │ finalized          │  ┌─ Query Router     │
                                    ▼                    │  │  (heuristic)      │
                         ┌─────────────────────┐        │  │                   │
                         │   Cloud Function     │        │  ├─ "rag" ───────────┤──► RAG Chain
                         │  (document-ingestion)│        │  │                   │
                         └──────────┬───────────┘        │  ├─ "metrics" ───────┤──► LangGraph Agent
                                    │                    │  │                   │    ├─ BigQuery SQL
                    ┌───────────────┼───────────┐        │  └─ "hybrid" ────────┤    └─ Vector Search
                    ▼               ▼           ▼        │                     │
             ┌────────────┐ ┌──────────┐ ┌──────────┐   │  ├─ Input Validator  │
             │ Sanitizer  │ │ Chunker  │ │ Embedder │   │  ├─ Rate Limiter     │
             └────────────┘ └──────────┘ └────┬─────┘   │  └─ Query Logger     │
                                              │          └──────────┬──────────┘
                              ┌───────────────┼──────┐              │
                              ▼                      ▼    ┌─────────┼────────┐
                    ┌──────────────────┐      ┌──────────┐│         ▼        │
                    │    ChromaDB      │      │ BigQuery  ││  LLM Provider   │
                    │  (Cloud Run,     │      │ ingestion_││ (model-agnostic)│
                    │   GCS-backed)    │      │ log       ││                 │
                    └──────────────────┘      │ query_log ││ Vertex AI       │
                                              │ infra     ││ OR OpenRouter   │
                                              │ metrics   │└─────────────────┘
                                              └──────────┘
```

## Tech Stack

| Layer | Technology |
|---|---|
| Infrastructure | Terraform (HCL), GCP |
| Frontend | Next.js 15, React 19, TypeScript, Tailwind CSS |
| RAG Service | FastAPI, LangChain, Cloud Run (Python 3.12) |
| Agent | LangGraph ReAct agent (langgraph.prebuilt) |
| Query Router | Heuristic classifier with confidence scoring (~1ms, no LLM) |
| SQL Validation | sqlglot AST parser (strict/flex policy, table allowlist, fail-fast config) |
| Document Ingestion | Cloud Functions Gen 2 (Python 3.12) |
| Data Sanitization | Regex-based IP/secret redaction |
| Chunking | File-type-aware (markdown, YAML, config, fallback) |
| Embeddings | Vertex AI text-embedding-004 |
| LLM (Primary) | Gemini 2.0 Flash via Vertex AI |
| LLM (Secondary) | Claude via OpenRouter (model-agnostic swap) |
| Vector Store | ChromaDB on Cloud Run (GCS persistence) |
| Metrics Store | BigQuery (infrastructure_metrics dataset) |
| Observability | BigQuery (platform_observability dataset) |
| Auth | Cloud Run IAM (ID token), IAM service accounts |
| Secrets | GCP Secret Manager (OpenRouter API key) |
| Container Registry | Artifact Registry |
| Event Triggers | EventArc (GCS → Cloud Function) |

### SQL Policy Modes

The BigQuery SQL tool uses a configurable policy (`LABSIGHT_SQL_POLICY_MODE`) that controls what queries the agent can generate:

- **`strict`** (default, production): Requires fully-qualified table names (`project.dataset.table`), validates table names against an explicit allowlist (`LABSIGHT_SQL_ALLOWED_TABLES`), rejects table-less queries. Empty allowlist fails startup.
- **`flex`** (development): Allows unqualified tables and table-less queries (`SELECT 1`). Project/dataset checks still enforced when qualifiers are present.

IAM `dataViewer` scoped to the infrastructure_metrics dataset is the primary enforcement layer. The SQL policy is defense-in-depth against the LLM generating queries that reference tables outside the expected set.

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
├── service/                       # RAG + Agent service (Cloud Run)
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── app/
│   │   ├── main.py                # FastAPI app factory (lifespan)
│   │   ├── config.py              # Pydantic settings (LABSIGHT_ prefix)
│   │   ├── utils.py               # Shared SSE helper
│   │   ├── middleware/
│   │   │   └── rate_limit.py      # Per-IP sliding window rate limiter
│   │   ├── routers/
│   │   │   ├── chat.py            # /api/chat (routes by query classification)
│   │   │   ├── health.py          # /api/health
│   │   │   ├── upload.py          # /api/upload, /api/upload/status, /api/upload/recent
│   │   │   └── dashboard.py       # /api/dashboard/overview
│   │   ├── agent/
│   │   │   ├── router.py          # Heuristic query router (rag/metrics/hybrid)
│   │   │   ├── graph.py           # LangGraph ReAct agent
│   │   │   └── tools/
│   │   │       ├── bigquery_sql.py    # SQL validation (sqlglot) + execution
│   │   │       └── vector_retrieval.py # ChromaDB search tool
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
│   │       └── logger.py          # BigQuery query logging + router_confidence
│   └── tests/
│
├── frontend/                      # Next.js frontend (Cloud Run)
│   ├── Dockerfile
│   ├── package.json
│   ├── next.config.ts
│   ├── tailwind.config.ts
│   └── src/
│       ├── app/
│       │   ├── layout.tsx         # Root layout + NavBar (dark ops theme)
│       │   ├── chat/page.tsx      # Chat UI with SSE streaming
│       │   ├── upload/page.tsx    # Drag-and-drop upload + status polling
│       │   ├── dashboard/page.tsx # Metrics cards + data tables
│       │   └── api/               # Server-side proxy route handlers
│       ├── components/            # UI components
│       └── lib/
│           ├── backend.ts         # ID token auth + fetch wrapper
│           └── types.ts           # TypeScript interfaces
│
├── scripts/                       # Development utilities
│   ├── seed_metrics.py            # Seed BigQuery with synthetic metrics data
│   └── test_router_accuracy.py    # Golden query set for router accuracy
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
│       ├── bigquery/              # Observability + infrastructure_metrics datasets
│       ├── chromadb/              # ChromaDB Cloud Run service
│       ├── cloud-functions/       # Ingestion function
│       ├── cloud-run-rag/         # RAG service (Cloud Run + Secret Manager)
│       └── cloud-run-frontend/    # Frontend (Cloud Run, unauthenticated)
│
├── Makefile
├── CHANGELOG.md
└── .env.example
```

## Prerequisites

- GCP project with billing enabled
- [Terraform](https://developer.hashicorp.com/terraform/install) >= 1.5
- Python 3.12+
- Node.js 20+
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
python3 -m venv .venv && source .venv/bin/activate
pip install -r service/requirements.txt -r ingestion/requirements.txt pytest pytest-asyncio pytest-cov
make install-frontend  # required because `make test` includes frontend tests
make test

# Upload a test document (after infra is deployed)
make test-upload

# Seed BigQuery with synthetic metrics data
make seed-metrics

# Build and deploy the RAG service
make build-service
make deploy-service

# Build and deploy frontend
make build-frontend
make deploy-frontend

# Run router accuracy check
make test-router-accuracy

# Local development
make dev-service     # Backend on :8080
make dev-frontend    # Frontend on :3000

# Check logs
make logs-function
```

## Roadmap

- [x] **Phase 1:** GCP foundation — Terraform, GCS, IAM, billing budget
- [x] **Phase 2:** Document ingestion pipeline — sanitizer, chunker, embedder, Cloud Function
- [x] **Phase 3:** Core RAG service — FastAPI, model abstraction, retrieval chain, citations, streaming
- [x] **Phase 4:** Agent + BigQuery — heuristic router, LangGraph ReAct agent, BigQuery SQL tool, infrastructure_metrics dataset
- [x] **Phase 5A:** Frontend — Next.js chat UI (streaming SSE), file upload, dashboard, rate limiting
- [ ] **Phase 5B:** IAP + API Gateway — identity-aware proxy, rate limiting at edge
- [ ] **Phase 6:** RAG tuning — cross-encoder re-ranking, HNSW benchmarking
- [ ] **Phase 7:** Guardrails, ADK evaluation, CI/CD, polish

See [CHANGELOG.md](CHANGELOG.md) for detailed version history.

## Cost

Runs almost entirely within GCP free tier. Vertex AI embedding calls are fractions of a cent. Gemini 2.0 Flash has a generous free tier. Cloud Run scales to zero when idle. Billing alert set at $25/month as a safety net.
