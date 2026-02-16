"""Tests for the dashboard router: GET /api/dashboard/overview."""

from __future__ import annotations

from datetime import date, datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config import Settings
from app.routers import dashboard


def _make_app(settings: Settings) -> FastAPI:
    app = FastAPI()
    app.include_router(dashboard.router)
    app.state.settings = settings
    return app


@pytest.fixture
def enabled_settings(settings: Settings) -> Settings:
    """Settings with dashboard enabled (both datasets configured)."""
    return Settings(
        **{
            **settings.model_dump(),
            "bigquery_observability_dataset": "test_observability",
            "bigquery_metrics_dataset": "test_infra_metrics",
        }
    )


@pytest.fixture
def client(settings: Settings) -> TestClient:
    """Client with dashboard disabled."""
    return TestClient(_make_app(settings))


@pytest.fixture
def enabled_client(enabled_settings: Settings) -> TestClient:
    """Client with dashboard enabled."""
    return TestClient(_make_app(enabled_settings))


class TestDashboardOverview:
    def test_disabled_returns_503(self, client: TestClient) -> None:
        resp = client.get("/api/dashboard/overview")
        assert resp.status_code == 503
        assert "not configured" in resp.json()["detail"]

    def test_obs_only_returns_503(self, settings: Settings) -> None:
        """Dashboard requires BOTH datasets — obs only is not enough."""
        s = Settings(
            **{**settings.model_dump(), "bigquery_observability_dataset": "obs"}
        )
        client = TestClient(_make_app(s))
        resp = client.get("/api/dashboard/overview")
        assert resp.status_code == 503

    @patch("app.routers.dashboard.bigquery")
    def test_returns_all_sections(
        self, mock_bq: MagicMock, enabled_client: TestClient
    ) -> None:
        mock_client = MagicMock()
        mock_bq.Client.return_value = mock_client

        # Each query returns one mock row as a dict
        health_row = {
            "service_name": "adguard",
            "status": "up",
            "response_time_ms": 12.3,
            "checked_at": datetime(2026, 2, 15, 12, 0, 0, tzinfo=timezone.utc),
        }
        uptime_row = {
            "service_name": "adguard",
            "uptime_percent": 99.5,
            "total_checks": 168,
            "avg_response_ms": 15.2,
        }
        resource_row = {
            "node": "pve01",
            "cpu_percent": 22.1,
            "memory_percent": 48.3,
            "storage_percent": 37.8,
            "collected_at": datetime(2026, 2, 15, 12, 0, 0, tzinfo=timezone.utc),
        }
        query_row = {
            "query_date": date(2026, 2, 15),
            "total_queries": 42,
            "successful": 40,
            "failed": 2,
            "avg_latency_ms": 1250.3,
            "rag_queries": 30,
            "metrics_queries": 8,
            "hybrid_queries": 4,
        }
        ingestion_row = {
            "file_name": "dns-setup.md",
            "file_type": "md",
            "status": "success",
            "chunk_count": 8,
            "total_time_ms": 2100.0,
            "timestamp": datetime(2026, 2, 15, 12, 0, 0, tzinfo=timezone.utc),
        }

        mock_client.query.return_value.result.return_value = iter(
            [MagicMock(**{"__iter__": lambda s: iter([health_row]), "items": health_row.items})]
        )

        # Simpler approach: make each query().result() return an iterable of dicts
        results = [
            [health_row],
            [uptime_row],
            [resource_row],
            [query_row],
            [ingestion_row],
        ]
        call_idx = {"i": 0}

        def fake_query(sql, **kwargs):
            idx = call_idx["i"]
            call_idx["i"] += 1
            mock_result = MagicMock()
            mock_result.result.return_value = results[idx] if idx < len(results) else []
            return mock_result

        mock_client.query.side_effect = fake_query

        resp = enabled_client.get("/api/dashboard/overview")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["service_health"]) == 1
        assert len(data["uptime_summary"]) == 1
        assert len(data["resource_utilization"]) == 1
        assert len(data["query_activity"]) == 1
        assert len(data["recent_ingestions"]) == 1

    @patch("app.routers.dashboard.bigquery")
    def test_partial_failure_returns_empty_section(
        self, mock_bq: MagicMock, enabled_client: TestClient
    ) -> None:
        """If one query fails, that section returns [] but others succeed."""
        mock_client = MagicMock()
        mock_bq.Client.return_value = mock_client

        call_idx = {"i": 0}

        def fake_query(sql, **kwargs):
            idx = call_idx["i"]
            call_idx["i"] += 1
            if idx == 0:
                raise Exception("BQ error on first query")
            mock_result = MagicMock()
            mock_result.result.return_value = []
            return mock_result

        mock_client.query.side_effect = fake_query

        resp = enabled_client.get("/api/dashboard/overview")
        assert resp.status_code == 200
        data = resp.json()
        # First section failed → []
        assert data["service_health"] == []
        # Others should be []  (empty but not failed)
        assert data["uptime_summary"] == []

    @patch("app.routers.dashboard.bigquery")
    def test_empty_datasets(
        self, mock_bq: MagicMock, enabled_client: TestClient
    ) -> None:
        """Empty datasets should return [] for all sections."""
        mock_client = MagicMock()
        mock_bq.Client.return_value = mock_client

        mock_result = MagicMock()
        mock_result.result.return_value = []
        mock_client.query.return_value = mock_result

        resp = enabled_client.get("/api/dashboard/overview")
        assert resp.status_code == 200
        data = resp.json()
        for key in [
            "service_health",
            "uptime_summary",
            "resource_utilization",
            "query_activity",
            "recent_ingestions",
        ]:
            assert data[key] == []

    @patch("app.routers.dashboard.bigquery")
    def test_data_shape(
        self, mock_bq: MagicMock, enabled_client: TestClient
    ) -> None:
        """Response has exactly the expected top-level keys."""
        mock_client = MagicMock()
        mock_bq.Client.return_value = mock_client
        mock_result = MagicMock()
        mock_result.result.return_value = []
        mock_client.query.return_value = mock_result

        resp = enabled_client.get("/api/dashboard/overview")
        assert resp.status_code == 200
        data = resp.json()
        expected_keys = {
            "service_health",
            "uptime_summary",
            "resource_utilization",
            "query_activity",
            "recent_ingestions",
        }
        assert set(data.keys()) == expected_keys

    @patch("app.routers.dashboard.bigquery")
    def test_bq_client_failure_returns_500(
        self, mock_bq: MagicMock, enabled_client: TestClient
    ) -> None:
        """If BigQuery client creation fails, return 500."""
        mock_bq.Client.side_effect = Exception("Auth failed")
        resp = enabled_client.get("/api/dashboard/overview")
        assert resp.status_code == 500
