"""BigQuery query logging for platform observability.

Best-effort: if the table isn't configured or the insert fails, we log
the error and move on. A failed analytics write should never break a
user query.
"""

from __future__ import annotations

import datetime
import logging
from typing import Any

logger = logging.getLogger(__name__)


def log_query(
    table_id: str,
    *,
    query: str,
    query_mode: str = "rag",
    model_used: str,
    retrieval_count: int = 0,
    latency_ms: float = 0,
    status: str = "success",
    error_message: str | None = None,
    router_confidence: float | None = None,
) -> None:
    """Insert a row into the query_log BigQuery table.

    Silently skipped if table_id is empty (logging disabled).
    """
    if not table_id:
        return

    try:
        from google.cloud import bigquery

        bq_client = bigquery.Client()

        row: dict[str, Any] = {
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "query": query[:1000],
            "query_mode": query_mode,
            "model_used": model_used,
            "retrieval_count": retrieval_count,
            "latency_ms": round(latency_ms, 1),
            "status": status,
            "error_message": error_message[:1024] if error_message else None,
            "router_confidence": round(router_confidence, 4) if router_confidence is not None else None,
        }

        errors = bq_client.insert_rows_json(table_id, [row])
        if errors:
            logger.error("BigQuery insert errors: %s", errors)

    except Exception:
        logger.exception("Failed to log query to BigQuery")
