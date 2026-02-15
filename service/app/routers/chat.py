"""Chat endpoint: query the RAG pipeline.

Supports two modes via the `stream` field in the request body:
  - stream=false (default): returns a complete JSON response
  - stream=true: returns an SSE stream of token chunks + sources
"""

from __future__ import annotations

import json
import logging
from typing import AsyncIterator

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.guardrails.input_validator import validate_query
from app.observability.logger import log_query
from app.rag.chain import RAGChain

logger = logging.getLogger(__name__)

router = APIRouter()


class ChatRequest(BaseModel):
    query: str
    stream: bool = False


class ChatResponse(BaseModel):
    answer: str
    sources: list[dict]
    model: str
    latency_ms: float
    retrieval_count: int


async def _logged_stream(
    raw_stream: AsyncIterator[str],
    table_id: str,
    query: str,
) -> AsyncIterator[str]:
    """Wrap a raw SSE stream to capture the done event and log the query.

    Yields every event unchanged, then parses the final "done" event to
    extract model/latency/retrieval_count for BigQuery logging.
    """
    model_used = ""
    latency_ms = 0.0
    retrieval_count = 0

    async for event in raw_stream:
        yield event

        # Parse the done event for metadata (best-effort)
        if '"type": "done"' in event:
            try:
                payload = json.loads(event.removeprefix("data: ").strip())
                model_used = payload.get("model", "")
                latency_ms = payload.get("latency_ms", 0.0)
                retrieval_count = payload.get("retrieval_count", 0)
            except (json.JSONDecodeError, ValueError):
                pass

    # Log after stream completes
    log_query(
        table_id,
        query=query,
        model_used=model_used,
        retrieval_count=retrieval_count,
        latency_ms=latency_ms,
    )


@router.post("/api/chat", response_model=None)
async def chat(body: ChatRequest, request: Request) -> ChatResponse | StreamingResponse:
    settings = request.app.state.settings
    chain: RAGChain = request.app.state.chain

    # Validate input
    query = validate_query(body.query, settings.max_query_length)

    if body.stream:
        return StreamingResponse(
            _logged_stream(
                chain.stream(query),
                settings.bigquery_query_log_table,
                query,
            ),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    # Non-streaming
    result = chain.invoke(query)

    # Best-effort observability logging
    log_query(
        settings.bigquery_query_log_table,
        query=query,
        model_used=result.model,
        retrieval_count=result.retrieval_count,
        latency_ms=result.latency_ms,
    )

    return ChatResponse(
        answer=result.answer,
        sources=[
            {
                "index": s.index,
                "content": s.content,
                "similarity_score": s.similarity_score,
                "metadata": s.metadata,
            }
            for s in result.sources
        ],
        model=result.model,
        latency_ms=round(result.latency_ms, 1),
        retrieval_count=result.retrieval_count,
    )
