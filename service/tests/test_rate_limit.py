"""Tests for per-IP rate limiting middleware."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from app.middleware.rate_limit import RateLimitMiddleware


def _make_app(rules: dict[str, int], window_seconds: int = 60) -> FastAPI:
    app = FastAPI()
    app.add_middleware(
        RateLimitMiddleware, rules=rules, window_seconds=window_seconds
    )

    @app.post("/api/chat")
    async def chat() -> dict[str, str]:
        return {"msg": "ok"}

    @app.post("/api/upload")
    async def upload() -> dict[str, str]:
        return {"msg": "ok"}

    @app.get("/api/upload/status")
    async def upload_status() -> dict[str, str]:
        return {"status": "processing"}

    @app.get("/api/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


class TestRateLimitMiddleware:
    def test_triggers_429_after_threshold(self) -> None:
        app = _make_app({"/api/upload": 3})
        client = TestClient(app)

        for _ in range(3):
            resp = client.post("/api/upload")
            assert resp.status_code == 200

        resp = client.post("/api/upload")
        assert resp.status_code == 429
        assert "Rate limit" in resp.json()["detail"]

    def test_retry_after_header(self) -> None:
        app = _make_app({"/api/upload": 1})
        client = TestClient(app)

        client.post("/api/upload")
        resp = client.post("/api/upload")
        assert resp.status_code == 429
        assert "Retry-After" in resp.headers

    def test_unmatched_path_not_limited(self) -> None:
        app = _make_app({"/api/upload": 1})
        client = TestClient(app)

        # Health endpoint should never be rate limited
        for _ in range(10):
            resp = client.get("/api/health")
            assert resp.status_code == 200

    def test_different_paths_independent(self) -> None:
        app = _make_app({"/api/upload": 2, "/api/chat": 2})
        client = TestClient(app)

        # Exhaust upload limit
        for _ in range(2):
            client.post("/api/upload")
        assert client.post("/api/upload").status_code == 429

        # Chat should still work
        assert client.post("/api/chat").status_code == 200

    def test_upload_status_not_throttled_by_upload_rule(self) -> None:
        """GET /api/upload/status must not be throttled by the /api/upload rule."""
        app = _make_app({"/api/upload": 1})
        client = TestClient(app)

        # Exhaust the /api/upload limit
        client.post("/api/upload")
        assert client.post("/api/upload").status_code == 429

        # Polling the status sub-path should still succeed (exact match only)
        for _ in range(20):
            resp = client.get("/api/upload/status")
            assert resp.status_code == 200
