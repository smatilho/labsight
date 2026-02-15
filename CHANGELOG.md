# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- SQL policy settings hardening: `sql_policy_mode` now validated as `strict|flex` at config load
- Fail-fast startup validation: strict mode now requires non-empty `LABSIGHT_SQL_ALLOWED_TABLES`
- Defensive SQL validator guards for unknown policy mode and strict-empty allowlist direct callers
- SQL blocked-function normalization covers both namespaced and typed sqlglot nodes (for example `ML.PREDICT` parsed as `Predict`)
- Regression tests for policy validation and typed ML function blocking

### Changed

- Test suite snapshot now 119 service tests + 37 ingestion tests (156 total)
- README setup command now installs both service and ingestion dependencies before `make test`

## [0.4.0] - 2026-02-15

### Added

- Heuristic query router: classifies queries as `rag`, `metrics`, or `hybrid` with confidence scoring and low-confidence fallback rules (~1ms, no LLM call, deterministic)
- LangGraph ReAct agent with two tools for metrics and hybrid query modes
- BigQuery SQL tool: sqlglot AST-based validation (SELECT-only allowlist, single-statement enforcement, project/dataset table allowlist, auto-appended LIMIT 1000), 100MB bytes_billed cap, 30s timeout, 50KB response payload cap
- Vector retrieval tool: wraps existing ChromaDB retriever with structured `ToolResult` return type for agent consumption
- `infrastructure_metrics` BigQuery dataset with 3 tables: `uptime_events` (partitioned by `checked_at`), `resource_utilization` (partitioned by `collected_at`), `service_inventory`
- Agent streaming via `astream_events(version="v2")`: SSE events for `tool_call`, `tool_result`, `token`, and `done`
- `router_confidence` column on `query_log` table for ongoing router quality measurement
- Seed data script (`scripts/seed_metrics.py`): generates 14 days of synthetic uptime checks, resource utilization, and service inventory with idempotent `--replace`/`--append` modes
- Router accuracy script (`scripts/test_router_accuracy.py`): 20 golden queries with expected classifications, prints accuracy report, exits non-zero below 80%
- Makefile targets: `seed-metrics`, `test-router-accuracy`
- Graceful degradation: agent is `None` when `LABSIGHT_BIGQUERY_METRICS_DATASET` is unset; all queries fall back to RAG mode
- 50 new unit tests: router (18), BigQuery SQL tool (15), vector retrieval tool (5), agent graph (4), chat routing (8)

### Changed

- Query taxonomy standardized: `agentic` renamed to `metrics` in BigQuery schema description and router
- Chat endpoint dispatches by router classification: RAG-only queries bypass the agent entirely (zero regression risk)
- `sse_event()` helper extracted to `app/utils.py` and shared between RAG chain and agent streaming
- Makefile uses `PYTHON ?= python3` for macOS portability (overridable via `make test PYTHON=python`)
- `.env.example` updated with `LABSIGHT_BIGQUERY_METRICS_DATASET`

### Removed

- Unused ChromaDB token secret resources from Terraform (5 resources: `random_password`, `google_secret_manager_secret`, secret version, 2 IAM bindings) — ChromaDB 1.x removed built-in token auth
- `random` provider from Terraform (only used by deleted secret)
- Unnecessary Cloud Run self-invoker IAM binding (RAG service doesn't call itself)
- Project-level `secretmanager.secretAccessor` binding on ingestion SA (no longer needed)

### Security

- BigQuery IAM separation: RAG SA gets `roles/bigquery.dataViewer` (read-only) on `infrastructure_metrics` dataset, keeps `roles/bigquery.dataEditor` on `platform_observability`
- SQL injection prevention via sqlglot AST parsing — catches comment-based attacks, case tricks, aliased subqueries, and multi-statement injection that keyword regex would miss

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

[Unreleased]: https://github.com/smatilho/labsight/compare/v0.4.0...HEAD
[0.4.0]: https://github.com/smatilho/labsight/releases/tag/v0.4.0
[0.3.0]: https://github.com/smatilho/labsight/releases/tag/v0.3.0
[0.2.0]: https://github.com/smatilho/labsight/releases/tag/v0.2.0
[0.1.0]: https://github.com/smatilho/labsight/releases/tag/v0.1.0
