# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.0] - 2026-02-15

### Added

- Core RAG service: FastAPI app with retrieval-augmented generation and source citations
- Model-agnostic LLM provider abstraction: swap Gemini (Vertex AI) ↔ Claude (OpenRouter) via config
- ChromaDB retriever as a LangChain `BaseRetriever` with Cloud Run IAM authentication
- RAG chain with `[Source N]` citation format, streaming (SSE) and non-streaming modes
- Input validation with prompt injection detection (heuristic patterns for ignore/override attempts)
- BigQuery query logging for platform observability (`query_log` table)
- Streaming query logging: `_logged_stream()` wrapper captures metadata from SSE `done` events
- Stream error handling: exceptions yield `{"type": "error"}` + `{"type": "done"}` so frontends never hang
- Pydantic-based settings (`LABSIGHT_` env prefix) with fail-fast validation at startup
- FastAPI lifespan context manager for resource initialization (settings, provider, retriever, chain)
- Cloud Run Terraform module (`cloud-run-rag`) for the RAG service deployment
- Artifact Registry Terraform resource for Docker image storage
- OpenRouter API key stored in Secret Manager (conditional — only when key is provided)
- Non-root Docker user (`labsight`, UID 1000) for container security
- Health endpoint (`/api/health`)
- Makefile targets: `test-service`, `dev-service`, `build-service`, `deploy-service`
- `.env.example` updated with Phase 3 variables
- 39 unit tests across chain, chat, health, input validation, LLM providers, and retriever

### Changed

- BigQuery IAM scoped to dataset level (`google_bigquery_dataset_iam_member`) instead of project-level `roles/bigquery.dataEditor` — both ingestion and RAG service accounts now have least-privilege access
- Architecture shifted from GKE to Cloud Run for the RAG service — GKE Autopilot management fee (~$72/month) exceeds the $25 billing alert; Cloud Run scales to zero with identical containerization

### Fixed

- ChromaDB retriever no longer caches the HTTP client — creates a fresh client with a new ID token on every call to prevent stale token failures (Google ID tokens expire after 1 hour)
- ChromaDB version sync documented in `service/requirements.txt` (must match `terraform/modules/chromadb/main.tf` image tag)

## [0.2.0] - 2026-02-15

### Added

- Document ingestion pipeline: sanitizer, chunker, embedder, Cloud Function entry point
- Data sanitizer strips RFC 1918 private IPs and secrets with consistent placeholders
- File-type-aware chunking: markdown (by headers), YAML (by top-level keys), config (by sections), fallback (sliding window)
- Vertex AI text-embedding-004 integration with batch support
- BigQuery `platform_observability` dataset with `ingestion_log` table (day-partitioned)
- ChromaDB on Cloud Run with GCS-backed persistence (Cloud Run IAM auth)
- Cloud Function Gen 2 triggered by GCS uploads with EventArc
- IAM bindings for ingestion service account (storage, Vertex AI, BigQuery, Secret Manager, Cloud Run invoker)
- Terraform modules: `bigquery`, `chromadb`, `cloud-functions`
- GCS buckets for function artifacts and ChromaDB persistence
- Phase 2 GCP APIs: Cloud Functions, Cloud Build, EventArc, Cloud Run, Vertex AI, Artifact Registry, Secret Manager
- File size guard (10 MB) rejects oversized uploads before download to prevent OOM
- Generation-based chunk IDs prevent data corruption on concurrent same-file uploads
- Unit tests for sanitizer, chunker, and embedder (37 tests)
- Test fixtures: sample markdown doc and docker-compose YAML
- Makefile targets: `test-ingestion`, `logs-function`, `test-upload`
- This changelog

### Fixed

- IP regex now validates octets (0-255) — previously matched invalid addresses like `10.999.999.999`
- Secret sanitizer now catches quoted values (`password="val"`, `api_key='val'`) — previously skipped them entirely
- Error-path BigQuery logging wrapped defensively so BQ failures can't mask the original exception

## [0.1.0] - 2026-02-13

### Added

- GCP project foundation with Terraform remote state on GCS
- Terraform modules: `gcs` (uploads bucket), `iam` (3 service accounts), `monitoring` (billing budget)
- 8 Phase 1 APIs enabled via Terraform
- Billing budget alert at $25 threshold
- `.gitignore`, `.env.example`, `Makefile` with Terraform targets

[Unreleased]: https://github.com/smatilho/labsight/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/smatilho/labsight/releases/tag/v0.3.0
[0.2.0]: https://github.com/smatilho/labsight/releases/tag/v0.2.0
[0.1.0]: https://github.com/smatilho/labsight/releases/tag/v0.1.0
