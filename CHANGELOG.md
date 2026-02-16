# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- IAP module now provisions the IAP service identity and frontend `roles/run.invoker` binding in Terraform (`google_project_service_identity` + `google_cloud_run_v2_service_iam_member`)

### Changed

- Terraform now requires explicit IAP OAuth credentials in IAP mode (`iap_oauth_client_id` + `iap_oauth_client_secret`) and fails fast if they are missing
- Terraform now requires non-empty `iap_members` when IAP mode is enabled
- IAP setup guidance now uses Google Auth Platform OAuth client flow (`gcloud iap oauth-brands` is deprecated/non-functional for many non-org projects)

### Fixed

- IAP runtime failure `The IAP service account is not provisioned` is now prevented by Terraform-managed service identity + invoker binding
- API Gateway managed service is now auto-enabled by Terraform to prevent `PERMISSION_DENIED: API ... is not enabled for the project` 403s

## [0.5.1] - 2026-02-15

### Added

- Identity-Aware Proxy (IAP) on frontend: HTTPS load balancer with managed SSL certificate, static IP, IAP-enforced Google account access control
- API Gateway module: OpenAPI spec-driven routing from frontend to RAG backend, per-route deadlines (5s–300s), API key validation via `x-api-key` header
- API key lifecycle: `google_apikeys_key` restricted to gateway's managed service, stored in Secret Manager, frontend SA has `secretAccessor`
- Gateway service account (`labsight-gateway`) with `roles/run.invoker` on RAG service — gateway authenticates to backend with signed JWT
- Frontend auth mode switching: `BACKEND_AUTH_MODE` env var selects between `id_token` (direct Cloud Run) and `api_key` (API Gateway) auth strategies
- HTTP-to-HTTPS redirect (port 80 → 443) via separate forwarding rule
- `google-beta` provider for API Gateway resources (`google_api_gateway_api`, `google_api_gateway_api_config`, `google_api_gateway_gateway`)
- Terraform variables: `domain`, `iap_members`, `frontend_public` — IAP and API Gateway are conditional on `domain != ""`
- 4 new frontend tests for backend auth mode switching (id_token, api_key, localhost skip, missing key warning)

### Changed

- Frontend Cloud Run ingress: `INGRESS_TRAFFIC_INTERNAL_LOAD_BALANCER` when IAP-protected (was `INGRESS_TRAFFIC_ALL`); `allUsers` invoker now conditional on `frontend_public`
- Frontend `backend.ts` rewritten to support dual auth modes — API key mode sends `x-api-key` header, ID token mode uses `google-auth-library`
- Billing budget raised from $25 to $50 (HTTPS LB adds ~$18/month ongoing cost)
- Test suite: 148 service + 37 ingestion + 27 frontend = **212 total** (was 208)
- README architecture diagram updated with IAP + API Gateway layers
- `.env.example` updated with `BACKEND_AUTH_MODE`, `BACKEND_API_KEY`, `TF_VAR_domain`, `TF_VAR_iap_members`, `TF_VAR_frontend_public`
- Terraform root check now fails fast if `domain` is set with `frontend_public=true` to prevent bypassing IAP
- Frontend module now forces non-public mode when `domain` is set (`frontend_public` only applies in non-IAP mode)
- API Gateway `api_config_id` is now content-hashed to support reliable `create_before_destroy` updates
- IAP module resource names now include environment suffixes to avoid `dev/staging/prod` naming collisions
- `terraform.tfvars.example` now matches the Phase 5B budget baseline (`budget_amount = 50`)

### Fixed

- Cloud Run frontend no longer sets reserved `PORT` env var (deployment rejected by Cloud Run)
- Frontend Docker build no longer fails when `public/` is absent; builder stage now guarantees `/app/public` exists before runtime copy
- `jest.setup.ts` TextEncoder/TextDecoder polyfill now aliases `util` symbols to avoid TypeScript redeclaration errors during `next build`
- Terraform apply ordering hardened: frontend module explicitly waits for API Gateway resources in IAP mode so Secret Manager-backed API key env injection does not race missing secret versions
- API key creation collision mitigation: key name versioned (`-v2`) to avoid API Keys control-plane tombstone conflicts after delete/recreate cycles

### Security

- IAP replaces `allUsers` as the frontend access control — only listed Google accounts can reach the frontend
- API Gateway validates API keys before forwarding to backend — defense-in-depth alongside Cloud Run IAM
- Gateway SA is a separate identity from frontend SA — principle of least privilege for backend invocation

## [0.5.0] - 2026-02-15

### Added

- Next.js 15 frontend deployed on Cloud Run with dark ops-style theme (slate-950/emerald/amber)
- Chat page: streaming SSE with tool call indicators, source citations, query mode badges, model/latency metadata
- Upload page: drag-and-drop file upload to GCS via backend proxy, ingestion status polling (3s interval, 60s timeout), recent ingestions table
- Dashboard page: metric cards (services up, uptime %, queries, latency) + 5 data tables (service health, uptime summary, resource utilization, query activity, recent ingestions)
- Server-side proxy route handlers with `google-auth-library` ID token auth — no CORS issues, no tokens exposed to browser
- Backend: `POST /api/upload` — multipart upload to GCS with unique object keys (`uploads/YYYY/MM/DD/<uuid>-<safe_name>`), filename sanitization, extension/size validation
- Backend: `GET /api/upload/status` — ingestion status from BigQuery (`processing`/`success`/`error`)
- Backend: `GET /api/upload/recent` — 20 most recent ingestion events
- Backend: `GET /api/dashboard/overview` — 5 aggregated BigQuery queries with partial failure resilience (each section returns `[]` independently)
- Per-IP sliding window rate limiter (`RateLimitMiddleware`): upload 5 req/min, chat 20 req/min, returns 429 with `Retry-After` header
- Terraform `cloud-run-frontend` module: Cloud Run v2, Gen2 execution, 0-2 instances, unauthenticated (`allUsers` invoker for Phase 5A, IAP deferred to 5B)
- Terraform: `labsight-frontend` service account, RAG uploads writer IAM binding, frontend invoker binding on RAG service
- SQL policy settings hardening: `sql_policy_mode` now validated as `strict|flex` at config load
- Fail-fast startup validation: strict mode now requires non-empty `LABSIGHT_SQL_ALLOWED_TABLES`
- Defensive SQL validator guards for unknown policy mode and strict-empty allowlist direct callers
- SQL blocked-function normalization covers both namespaced and typed sqlglot nodes
- 29 backend tests (upload, dashboard, rate limiting) + 23 frontend tests (components, route handlers)
- Makefile targets: `dev-frontend`, `test-frontend`, `build-frontend`, `deploy-frontend`, `install-frontend`
- Streaming chat now applies SSE `sources` events in the frontend so citations render during stream mode
- Tool call indicator mappings now include LangGraph-emitted tool names (`query_infrastructure_metrics`, `search_documents`)

### Changed

- Test suite snapshot now 148 service tests + 37 ingestion tests + 23 frontend tests (208 total)
- RAG service version bumped to 0.5.0
- `.env.example` updated with `LABSIGHT_GCS_UPLOADS_BUCKET` and `LABSIGHT_BIGQUERY_OBSERVABILITY_DATASET`
- README architecture diagram updated with frontend + upload flow
- `make test` now runs ingestion, service, and frontend test suites
- README quickstart now installs frontend dependencies before running `make test`
- Query mode badges are now color-coded by mode (`rag`/`metrics`/`hybrid`) in chat metadata
- Frontend `UploadStatusResponse` typing aligned to implemented backend states (`processing`/`success`/`error`)
- Documentation sync for Phase 5A: frontend public (`allUsers`) posture, upload status contract, and filename sanitization behavior

### Fixed

- Rate limiter now matches exact paths instead of prefixes, preventing `/api/upload/status` and `/api/upload/recent` from being throttled by `/api/upload` limits
- Upload status polling now handles non-2xx and malformed payloads safely (no UI crash path)
- Status badge rendering now guards null/undefined status values
- Dotless filename handling fixed so allowlisted `Dockerfile` uploads are accepted while unknown dotless names remain rejected

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

[Unreleased]: https://github.com/smatilho/labsight/compare/v0.5.1...HEAD
[0.5.1]: https://github.com/smatilho/labsight/compare/v0.5.0...v0.5.1
[0.5.0]: https://github.com/smatilho/labsight/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/smatilho/labsight/releases/tag/v0.4.0
[0.3.0]: https://github.com/smatilho/labsight/releases/tag/v0.3.0
[0.2.0]: https://github.com/smatilho/labsight/releases/tag/v0.2.0
[0.1.0]: https://github.com/smatilho/labsight/releases/tag/v0.1.0
