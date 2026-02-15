# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

[Unreleased]: https://github.com/smatilho/labsight/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/smatilho/labsight/releases/tag/v0.2.0
[0.1.0]: https://github.com/smatilho/labsight/releases/tag/v0.1.0
