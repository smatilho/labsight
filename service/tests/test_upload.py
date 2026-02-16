"""Tests for the upload router: POST /api/upload, GET /api/upload/status, GET /api/upload/recent."""

from __future__ import annotations

import io
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config import Settings
from app.routers import upload


def _make_app(settings: Settings) -> FastAPI:
    app = FastAPI()
    app.include_router(upload.router)
    app.state.settings = settings
    return app


@pytest.fixture
def enabled_settings(settings: Settings) -> Settings:
    """Settings with upload and observability enabled."""
    return Settings(
        **{
            **settings.model_dump(),
            "gcs_uploads_bucket": "test-uploads-bucket",
            "bigquery_observability_dataset": "test_observability",
        }
    )


@pytest.fixture
def client(settings: Settings) -> TestClient:
    """Client with upload disabled (default settings)."""
    return TestClient(_make_app(settings))


@pytest.fixture
def enabled_client(enabled_settings: Settings) -> TestClient:
    """Client with upload enabled."""
    return TestClient(_make_app(enabled_settings))


# --- POST /api/upload ---


class TestUploadFile:
    def test_disabled_returns_503(self, client: TestClient) -> None:
        resp = client.post(
            "/api/upload",
            files={"file": ("test.md", b"# Hello", "text/markdown")},
        )
        assert resp.status_code == 503
        assert "not configured" in resp.json()["detail"]

    def test_bad_extension_returns_400(self, enabled_client: TestClient) -> None:
        resp = enabled_client.post(
            "/api/upload",
            files={"file": ("malware.exe", b"evil", "application/octet-stream")},
        )
        assert resp.status_code == 400
        assert ".exe" in resp.json()["detail"]

    def test_too_large_returns_400(self, enabled_settings: Settings) -> None:
        small_limit = Settings(
            **{**enabled_settings.model_dump(), "max_upload_size_bytes": 100}
        )
        client = TestClient(_make_app(small_limit))
        resp = client.post(
            "/api/upload",
            files={"file": ("big.md", b"x" * 200, "text/markdown")},
        )
        assert resp.status_code == 400
        assert "exceeds maximum size" in resp.json()["detail"]

    @patch("app.routers.upload.storage")
    def test_success(self, mock_storage: MagicMock, enabled_client: TestClient) -> None:
        mock_client = MagicMock()
        mock_storage.Client.return_value = mock_client
        mock_bucket = MagicMock()
        mock_client.bucket.return_value = mock_bucket
        mock_blob = MagicMock()
        mock_bucket.blob.return_value = mock_blob

        resp = enabled_client.post(
            "/api/upload",
            files={"file": ("dns-setup.md", b"# DNS Setup", "text/markdown")},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["file_name"] == "dns-setup.md"
        assert data["object_name"].startswith("uploads/")
        assert data["object_name"].endswith("-dns-setup.md")
        assert data["bucket"] == "test-uploads-bucket"
        assert data["size_bytes"] == len(b"# DNS Setup")
        assert data["status"] == "uploaded"

        mock_blob.upload_from_string.assert_called_once_with(b"# DNS Setup")

    @patch("app.routers.upload.storage")
    def test_unique_object_keys(
        self, mock_storage: MagicMock, enabled_client: TestClient
    ) -> None:
        mock_client = MagicMock()
        mock_storage.Client.return_value = mock_client
        mock_client.bucket.return_value.blob.return_value = MagicMock()

        resp1 = enabled_client.post(
            "/api/upload",
            files={"file": ("test.md", b"a", "text/markdown")},
        )
        resp2 = enabled_client.post(
            "/api/upload",
            files={"file": ("test.md", b"b", "text/markdown")},
        )
        assert resp1.status_code == 200
        assert resp2.status_code == 200
        assert resp1.json()["object_name"] != resp2.json()["object_name"]

    @patch("app.routers.upload.storage")
    def test_gcs_error_returns_500(
        self, mock_storage: MagicMock, enabled_client: TestClient
    ) -> None:
        mock_client = MagicMock()
        mock_storage.Client.return_value = mock_client
        mock_bucket = MagicMock()
        mock_client.bucket.return_value = mock_bucket
        mock_blob = MagicMock()
        mock_blob.upload_from_string.side_effect = Exception("GCS down")
        mock_bucket.blob.return_value = mock_blob

        resp = enabled_client.post(
            "/api/upload",
            files={"file": ("test.md", b"# Hello", "text/markdown")},
        )
        assert resp.status_code == 500

    def test_no_file_returns_422(self, enabled_client: TestClient) -> None:
        resp = enabled_client.post("/api/upload")
        assert resp.status_code == 422

    @patch("app.routers.upload.storage")
    def test_dockerfile_accepted(
        self, mock_storage: MagicMock, enabled_client: TestClient
    ) -> None:
        """Dotless filenames like 'Dockerfile' should match against the allowlist."""
        mock_client = MagicMock()
        mock_storage.Client.return_value = mock_client
        mock_client.bucket.return_value.blob.return_value = MagicMock()

        resp = enabled_client.post(
            "/api/upload",
            files={"file": ("Dockerfile", b"FROM python:3.12", "application/octet-stream")},
        )
        assert resp.status_code == 200
        assert resp.json()["file_name"] == "Dockerfile"

    def test_unknown_dotless_rejected(self, enabled_client: TestClient) -> None:
        """Unknown dotless filenames are rejected."""
        resp = enabled_client.post(
            "/api/upload",
            files={"file": ("Makefile", b"all:", "application/octet-stream")},
        )
        assert resp.status_code == 400
        assert "not supported" in resp.json()["detail"]

    @patch("app.routers.upload.storage")
    def test_path_traversal_sanitized(
        self, mock_storage: MagicMock, enabled_client: TestClient
    ) -> None:
        mock_client = MagicMock()
        mock_storage.Client.return_value = mock_client
        mock_client.bucket.return_value.blob.return_value = MagicMock()

        resp = enabled_client.post(
            "/api/upload",
            files={"file": ("../../etc/passwd.md", b"hack", "text/markdown")},
        )
        assert resp.status_code == 200
        obj_name = resp.json()["object_name"]
        assert ".." not in obj_name
        assert obj_name.endswith("passwd.md")


# --- GET /api/upload/status ---


class TestUploadStatus:
    def test_disabled_returns_503(self, client: TestClient) -> None:
        resp = client.get("/api/upload/status", params={"file_name": "test.md"})
        assert resp.status_code == 503

    @patch("app.routers.upload.bigquery")
    def test_found_success(
        self, mock_bq: MagicMock, enabled_client: TestClient
    ) -> None:
        mock_client = MagicMock()
        mock_bq.Client.return_value = mock_client
        mock_bq.QueryJobConfig = MagicMock()
        mock_bq.ScalarQueryParameter = MagicMock()

        mock_row = MagicMock()
        mock_row.file_name = "uploads/2026/02/15/abc-test.md"
        mock_row.file_type = "md"
        mock_row.status = "success"
        mock_row.chunk_count = 8
        mock_row.chunks_sanitized = 3
        mock_row.total_time_ms = 1200.5
        mock_row.error_message = None
        mock_row.timestamp = datetime(2026, 2, 15, 12, 0, 0, tzinfo=timezone.utc)
        mock_client.query.return_value.result.return_value = [mock_row]

        resp = enabled_client.get(
            "/api/upload/status",
            params={"file_name": "uploads/2026/02/15/abc-test.md"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["chunk_count"] == 8

    @patch("app.routers.upload.bigquery")
    def test_found_error(
        self, mock_bq: MagicMock, enabled_client: TestClient
    ) -> None:
        mock_client = MagicMock()
        mock_bq.Client.return_value = mock_client
        mock_bq.QueryJobConfig = MagicMock()
        mock_bq.ScalarQueryParameter = MagicMock()

        mock_row = MagicMock()
        mock_row.file_name = "test.md"
        mock_row.file_type = "md"
        mock_row.status = "error"
        mock_row.chunk_count = None
        mock_row.chunks_sanitized = None
        mock_row.total_time_ms = None
        mock_row.error_message = "Parsing failed"
        mock_row.timestamp = datetime(2026, 2, 15, 12, 0, 0, tzinfo=timezone.utc)
        mock_client.query.return_value.result.return_value = [mock_row]

        resp = enabled_client.get(
            "/api/upload/status", params={"file_name": "test.md"}
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "error"

    @patch("app.routers.upload.bigquery")
    def test_processing_no_rows(
        self, mock_bq: MagicMock, enabled_client: TestClient
    ) -> None:
        mock_client = MagicMock()
        mock_bq.Client.return_value = mock_client
        mock_bq.QueryJobConfig = MagicMock()
        mock_bq.ScalarQueryParameter = MagicMock()
        mock_client.query.return_value.result.return_value = []

        resp = enabled_client.get(
            "/api/upload/status", params={"file_name": "new-file.md"}
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "processing"


# --- GET /api/upload/recent ---


class TestUploadRecent:
    def test_disabled_returns_503(self, client: TestClient) -> None:
        resp = client.get("/api/upload/recent")
        assert resp.status_code == 503

    @patch("app.routers.upload.bigquery")
    def test_returns_list(
        self, mock_bq: MagicMock, enabled_client: TestClient
    ) -> None:
        mock_client = MagicMock()
        mock_bq.Client.return_value = mock_client

        mock_row = MagicMock()
        mock_row.file_name = "dns-setup.md"
        mock_row.file_type = "md"
        mock_row.status = "success"
        mock_row.chunk_count = 5
        mock_row.chunks_sanitized = 1
        mock_row.total_time_ms = 800.0
        mock_row.error_message = None
        mock_row.timestamp = datetime(2026, 2, 15, 12, 0, 0, tzinfo=timezone.utc)
        mock_client.query.return_value.result.return_value = [mock_row]

        resp = enabled_client.get("/api/upload/recent")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["files"]) == 1
        assert data["files"][0]["file_name"] == "dns-setup.md"

    @patch("app.routers.upload.bigquery")
    def test_empty_list(
        self, mock_bq: MagicMock, enabled_client: TestClient
    ) -> None:
        mock_client = MagicMock()
        mock_bq.Client.return_value = mock_client
        mock_client.query.return_value.result.return_value = []

        resp = enabled_client.get("/api/upload/recent")
        assert resp.status_code == 200
        assert resp.json()["files"] == []
