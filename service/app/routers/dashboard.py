"""Dashboard overview endpoint: aggregated metrics from BigQuery.

GET /api/dashboard/overview — Returns service health, uptime summary,
resource utilization, query activity, and recent ingestions. Each section
returns [] on individual query failure (partial success design).
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from google.cloud import bigquery
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter()


class DashboardOverviewResponse(BaseModel):
    service_health: list[dict[str, Any]]
    uptime_summary: list[dict[str, Any]]
    resource_utilization: list[dict[str, Any]]
    query_activity: list[dict[str, Any]]
    recent_ingestions: list[dict[str, Any]]


def _run_query(client: Any, sql: str) -> list[dict[str, Any]]:
    """Execute a BigQuery query and return rows as dicts."""
    rows = client.query(sql).result()
    return [dict(row) for row in rows]


def _safe_query(client: Any, sql: str, label: str) -> list[dict[str, Any]]:
    """Run a query, returning [] on failure (partial success)."""
    try:
        return _run_query(client, sql)
    except Exception:
        logger.exception("Dashboard query failed: %s", label)
        return []


@router.get("/api/dashboard/overview", response_model=None)
async def dashboard_overview(
    request: Request,
) -> DashboardOverviewResponse | JSONResponse:
    settings = request.app.state.settings

    if not settings.bigquery_observability_dataset or not settings.bigquery_metrics_dataset:
        return JSONResponse(
            status_code=503,
            content={"detail": "Dashboard endpoint is not configured."},
        )

    try:
        client = bigquery.Client()
    except Exception:
        logger.exception("Failed to create BigQuery client")
        return JSONResponse(
            status_code=500,
            content={"detail": "Failed to connect to BigQuery."},
        )

    project = settings.gcp_project
    obs_ds = settings.bigquery_observability_dataset
    infra_ds = settings.bigquery_metrics_dataset

    # 1. Service health: latest status per service (24h)
    service_health = _safe_query(
        client,
        f"""
        SELECT service_name, status, response_time_ms, checked_at
        FROM `{project}.{infra_ds}.uptime_events`
        WHERE checked_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 24 HOUR)
        QUALIFY ROW_NUMBER() OVER (PARTITION BY service_name ORDER BY checked_at DESC) = 1
        ORDER BY service_name
        """,
        "service_health",
    )

    # 2. Uptime summary (7d)
    uptime_summary = _safe_query(
        client,
        f"""
        SELECT service_name,
               ROUND(SAFE_DIVIDE(COUNTIF(status = 'up'), COUNT(*)) * 100, 2) AS uptime_percent,
               COUNT(*) AS total_checks,
               ROUND(AVG(response_time_ms), 1) AS avg_response_ms
        FROM `{project}.{infra_ds}.uptime_events`
        WHERE checked_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)
        GROUP BY service_name
        ORDER BY service_name
        """,
        "uptime_summary",
    )

    # 3. Resource utilization: latest per node (24h)
    resource_utilization = _safe_query(
        client,
        f"""
        SELECT node, cpu_percent, memory_percent, storage_percent, collected_at
        FROM `{project}.{infra_ds}.resource_utilization`
        WHERE collected_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 24 HOUR)
        QUALIFY ROW_NUMBER() OVER (PARTITION BY node ORDER BY collected_at DESC) = 1
        ORDER BY node
        """,
        "resource_utilization",
    )

    # 4. Query activity: daily counts (7d)
    query_activity = _safe_query(
        client,
        f"""
        SELECT DATE(timestamp) AS query_date,
               COUNT(*) AS total_queries,
               COUNTIF(status = 'success') AS successful,
               COUNTIF(status != 'success') AS failed,
               ROUND(AVG(latency_ms), 1) AS avg_latency_ms,
               COUNTIF(query_mode = 'rag') AS rag_queries,
               COUNTIF(query_mode = 'metrics') AS metrics_queries,
               COUNTIF(query_mode = 'hybrid') AS hybrid_queries
        FROM `{project}.{obs_ds}.query_log`
        WHERE timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)
        GROUP BY query_date
        ORDER BY query_date DESC
        """,
        "query_activity",
    )

    # 5. Recent ingestions (last 10)
    recent_ingestions = _safe_query(
        client,
        f"""
        SELECT file_name, file_type, status, chunk_count,
               total_time_ms, timestamp
        FROM `{project}.{obs_ds}.ingestion_log`
        ORDER BY timestamp DESC
        LIMIT 10
        """,
        "recent_ingestions",
    )

    return DashboardOverviewResponse(
        service_health=service_health,
        uptime_summary=uptime_summary,
        resource_utilization=resource_utilization,
        query_activity=query_activity,
        recent_ingestions=recent_ingestions,
    )
