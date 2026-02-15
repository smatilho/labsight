"""Chat endpoint: query the RAG pipeline or LangGraph agent.

Supports three query modes via heuristic classification:
  - rag: documentation queries → RAGChain (unchanged Phase 3 path)
  - metrics: infrastructure metrics → LangGraph agent with BigQuery tool
  - hybrid: both docs + metrics → LangGraph agent with both tools

Each mode supports streaming (SSE) and non-streaming (JSON) responses.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import AsyncIterator

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse
from langchain_core.messages import AIMessage, HumanMessage
from pydantic import BaseModel

from app.agent.router import classify_query
from app.guardrails.input_validator import validate_query
from app.observability.logger import log_query
from app.rag.chain import RAGChain
from app.utils import sse_event

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
    query_mode: str = "rag"


class ErrorResponse(BaseModel):
    error: dict
    query_mode: str
    model: str
    latency_ms: float


def _error_response(
    *,
    query_mode: str,
    model_name: str,
    latency_ms: float,
    message: str,
) -> JSONResponse:
    """Build a structured HTTP 500 response for non-streaming failures."""
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            error={"type": "internal_error", "message": message},
            query_mode=query_mode,
            model=model_name,
            latency_ms=round(latency_ms, 1),
        ).model_dump(),
    )


# ---------------------------------------------------------------------------
# RAG path (unchanged from Phase 3)
# ---------------------------------------------------------------------------

async def _rag_logged_stream(
    raw_stream: AsyncIterator[str],
    table_id: str,
    query: str,
    router_confidence: float | None = None,
) -> AsyncIterator[str]:
    """Wrap a raw SSE stream to capture done/error events and log the query.

    Parses each SSE event as JSON to extract metadata. Tracks error events
    emitted by the RAG chain so the log entry reflects the true status.
    """
    model_used = ""
    latency_ms = 0.0
    retrieval_count = 0
    status = "success"
    error_message = None

    async for event in raw_stream:
        yield event

        line = event.removeprefix("data: ").strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            continue

        event_type = payload.get("type")
        if event_type == "error":
            status = "error"
            error_message = payload.get("message", "Unknown stream error")
        elif event_type == "done":
            model_used = payload.get("model", "")
            latency_ms = payload.get("latency_ms", 0.0)
            retrieval_count = payload.get("retrieval_count", 0)

    log_query(
        table_id,
        query=query,
        model_used=model_used,
        retrieval_count=retrieval_count,
        latency_ms=latency_ms,
        status=status,
        error_message=error_message,
        router_confidence=router_confidence,
    )


# ---------------------------------------------------------------------------
# Agent path (Phase 4)
# ---------------------------------------------------------------------------

async def _agent_stream(
    agent: object,
    query: str,
    model_name: str,
    table_id: str,
    query_mode: str,
    router_confidence: float | None = None,
) -> AsyncIterator[str]:
    """Stream SSE events from the LangGraph agent.

    Event types:
      - tool_call: agent is invoking a tool
      - tool_result: tool returned a result
      - token: LLM response token
      - done: final event with metadata
    """
    start = time.monotonic()
    status = "success"
    error_message = None

    try:
        input_msg = {"messages": [HumanMessage(content=query)]}

        async for event in agent.astream_events(input_msg, version="v2"):  # type: ignore[union-attr]
            kind = event.get("event", "")

            if kind == "on_tool_start":
                tool_name = event.get("name", "")
                yield sse_event({"type": "tool_call", "tool": tool_name})

            elif kind == "on_tool_end":
                tool_name = event.get("name", "")
                output = str(event.get("data", {}).get("output", ""))
                yield sse_event({
                    "type": "tool_result",
                    "tool": tool_name,
                    "result": output[:500],
                })

            elif kind == "on_chat_model_stream":
                chunk = event.get("data", {}).get("chunk")
                if chunk and hasattr(chunk, "content") and chunk.content:
                    # Only yield text content, skip tool call chunks
                    if isinstance(chunk.content, str):
                        yield sse_event({"type": "token", "content": chunk.content})

        latency_ms = (time.monotonic() - start) * 1000
        yield sse_event({
            "type": "done",
            "model": model_name,
            "latency_ms": round(latency_ms, 1),
            "query_mode": query_mode,
        })

    except asyncio.CancelledError:
        status = "cancelled"
        latency_ms = (time.monotonic() - start) * 1000
        raise

    except Exception:
        logger.exception("Error during agent streaming")
        status = "error"
        error_message = "An internal error occurred"
        latency_ms = (time.monotonic() - start) * 1000
        yield sse_event({"type": "error", "message": error_message})
        yield sse_event({
            "type": "done",
            "model": model_name,
            "latency_ms": round(latency_ms, 1),
            "query_mode": query_mode,
        })

    finally:
        log_query(
            table_id,
            query=query,
            query_mode=query_mode,
            model_used=model_name,
            latency_ms=(time.monotonic() - start) * 1000,
            status=status,
            error_message=error_message,
            router_confidence=router_confidence,
        )


async def _agent_invoke(
    agent: object,
    query: str,
    model_name: str,
    query_mode: str,
    table_id: str,
    router_confidence: float | None = None,
) -> ChatResponse | JSONResponse:
    """Non-streaming agent invocation with error handling and logging."""
    start = time.monotonic()
    status = "success"
    error_message = None

    try:
        input_msg = {"messages": [HumanMessage(content=query)]}
        result = await agent.ainvoke(input_msg)  # type: ignore[union-attr]

        latency_ms = (time.monotonic() - start) * 1000

        # Extract the final AI message
        messages = result.get("messages", [])
        answer = ""
        for msg in reversed(messages):
            if isinstance(msg, AIMessage) and isinstance(msg.content, str):
                answer = msg.content
                break

        return ChatResponse(
            answer=answer,
            sources=[],
            model=model_name,
            latency_ms=round(latency_ms, 1),
            retrieval_count=0,
            query_mode=query_mode,
        )

    except Exception:
        logger.exception("Error during agent invocation")
        status = "error"
        error_message = "An internal error occurred during agent processing."
        latency_ms = (time.monotonic() - start) * 1000

        return _error_response(
            query_mode=query_mode,
            model_name=model_name,
            latency_ms=latency_ms,
            message=error_message,
        )

    finally:
        log_query(
            table_id,
            query=query,
            query_mode=query_mode,
            model_used=model_name,
            latency_ms=(time.monotonic() - start) * 1000,
            status=status,
            error_message=error_message,
            router_confidence=router_confidence,
        )


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@router.post("/api/chat", response_model=None)
async def chat(body: ChatRequest, request: Request) -> ChatResponse | StreamingResponse:
    settings = request.app.state.settings
    chain: RAGChain = request.app.state.chain
    agent = getattr(request.app.state, "agent", None)
    model_name = request.app.state.provider.get_model_name()

    # Validate input
    query = validate_query(body.query, settings.max_query_length)

    # Classify query
    classification = classify_query(query)
    query_mode = classification.mode

    # If agent isn't available, fall back to RAG for everything
    if agent is None and query_mode in ("metrics", "hybrid"):
        query_mode = "rag"

    # --- RAG path (rag mode or fallback) ---
    if query_mode == "rag":
        if body.stream:
            return StreamingResponse(
                _rag_logged_stream(
                    chain.stream(query),
                    settings.bigquery_query_log_table,
                    query,
                    router_confidence=classification.confidence,
                ),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "X-Accel-Buffering": "no",
                },
            )

        start = time.monotonic()
        status = "success"
        error_message = None

        try:
            result = chain.invoke(query)

            log_query(
                settings.bigquery_query_log_table,
                query=query,
                model_used=result.model,
                retrieval_count=result.retrieval_count,
                latency_ms=result.latency_ms,
                router_confidence=classification.confidence,
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
                query_mode="rag",
            )

        except Exception:
            logger.exception("Error during RAG invocation")
            error_message = "An internal error occurred while processing your query."
            latency_ms = (time.monotonic() - start) * 1000

            log_query(
                settings.bigquery_query_log_table,
                query=query,
                model_used=model_name,
                latency_ms=latency_ms,
                status="error",
                error_message=error_message,
                router_confidence=classification.confidence,
            )

            return _error_response(
                query_mode="rag",
                model_name=model_name,
                latency_ms=latency_ms,
                message=error_message,
            )

    # --- Agent path (metrics or hybrid) ---
    if body.stream:
        return StreamingResponse(
            _agent_stream(
                agent,
                query,
                model_name,
                settings.bigquery_query_log_table,
                query_mode,
                router_confidence=classification.confidence,
            ),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    return await _agent_invoke(
        agent,
        query,
        model_name,
        query_mode,
        settings.bigquery_query_log_table,
        router_confidence=classification.confidence,
    )
