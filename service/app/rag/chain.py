"""RAG chain: retriever + LLM with source citations.

Composes the ChromaDB retriever with a chat model to answer questions
about homelab infrastructure using retrieved document context. Every
claim must be cited with [Source N] references.

Supports two modes:
  - invoke(): returns a complete RAGResponse with answer + sources
  - stream(): yields SSE-formatted events for real-time streaming
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from typing import AsyncIterator

from langchain_core.documents import Document
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.retrievers import BaseRetriever

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
You are Labsight, an AI operations assistant for a self-hosted homelab \
infrastructure. Answer questions using ONLY the provided context documents. \
If the context doesn't contain enough information to answer, say so honestly.

Rules:
1. Cite every factual claim with [Source N] where N matches the source number.
2. If multiple sources support a claim, cite all of them: [Source 1][Source 2].
3. Keep answers concise and technical.
4. Never invent information not present in the sources.
5. Redacted values like [PRIVATE_IP_1] are intentional — do not try to guess \
the original values.
"""


@dataclass
class SourceDocument:
    """A retrieved source with its citation index."""

    index: int
    content: str
    metadata: dict
    similarity_score: float


@dataclass
class RAGResponse:
    """Complete response from the RAG chain."""

    answer: str
    sources: list[SourceDocument]
    model: str
    latency_ms: float
    retrieval_count: int


def _format_context(documents: list[Document]) -> tuple[str, list[SourceDocument]]:
    """Build numbered context block and source list from retrieved docs."""
    context_parts: list[str] = []
    sources: list[SourceDocument] = []

    for i, doc in enumerate(documents, start=1):
        source_label = doc.metadata.get("source", "unknown")
        context_parts.append(f"[Source {i}] (from {source_label}):\n{doc.page_content}")

        sources.append(
            SourceDocument(
                index=i,
                content=doc.page_content[:200],
                metadata=doc.metadata,
                similarity_score=doc.metadata.get("similarity_score", 0.0),
            )
        )

    return "\n\n".join(context_parts), sources


class RAGChain:
    """Retrieval-augmented generation with citations."""

    def __init__(
        self,
        retriever: BaseRetriever,
        llm: BaseChatModel,
        model_name: str,
    ) -> None:
        self._retriever = retriever
        self._llm = llm
        self._model_name = model_name

    def invoke(self, query: str) -> RAGResponse:
        """Run the full RAG pipeline and return a complete response."""
        start = time.monotonic()

        # Retrieve
        documents = self._retriever.invoke(query)
        if not documents:
            return RAGResponse(
                answer="I couldn't find any relevant documents to answer your question.",
                sources=[],
                model=self._model_name,
                latency_ms=(time.monotonic() - start) * 1000,
                retrieval_count=0,
            )

        # Build context and generate
        context, sources = _format_context(documents)
        messages = [
            SystemMessage(content=_SYSTEM_PROMPT),
            HumanMessage(
                content=f"Context:\n{context}\n\nQuestion: {query}"
            ),
        ]

        response = self._llm.invoke(messages)
        latency_ms = (time.monotonic() - start) * 1000

        logger.info(
            "RAG query completed in %.0fms (model=%s, sources=%d)",
            latency_ms,
            self._model_name,
            len(sources),
        )

        return RAGResponse(
            answer=response.content,
            sources=sources,
            model=self._model_name,
            latency_ms=latency_ms,
            retrieval_count=len(documents),
        )

    async def stream(self, query: str) -> AsyncIterator[str]:
        """Stream SSE events: token chunks followed by a final sources event.

        Event format:
          data: {"type": "token", "content": "..."}
          data: {"type": "sources", "sources": [...]}
          data: {"type": "done", "model": "...", "latency_ms": ...}

        On error, yields an error event + done so the frontend never hangs.
        """
        start = time.monotonic()

        try:
            documents = self._retriever.invoke(query)
            if not documents:
                yield _sse(
                    {"type": "token", "content": "I couldn't find any relevant documents to answer your question."}
                )
                yield _sse({"type": "done", "model": self._model_name, "latency_ms": 0, "retrieval_count": 0})
                return

            context, sources = _format_context(documents)
            messages = [
                SystemMessage(content=_SYSTEM_PROMPT),
                HumanMessage(
                    content=f"Context:\n{context}\n\nQuestion: {query}"
                ),
            ]

            async for chunk in self._llm.astream(messages):
                if chunk.content:
                    yield _sse({"type": "token", "content": chunk.content})

            # Send sources after all tokens
            sources_payload = [
                {
                    "index": s.index,
                    "content": s.content,
                    "similarity_score": s.similarity_score,
                    "metadata": s.metadata,
                }
                for s in sources
            ]
            yield _sse({"type": "sources", "sources": sources_payload})

            latency_ms = (time.monotonic() - start) * 1000
            yield _sse({
                "type": "done",
                "model": self._model_name,
                "latency_ms": round(latency_ms, 1),
                "retrieval_count": len(documents),
            })

        except Exception:
            logger.exception("Error during streaming RAG query")
            latency_ms = (time.monotonic() - start) * 1000
            yield _sse({"type": "error", "message": "An internal error occurred while generating a response."})
            yield _sse({
                "type": "done",
                "model": self._model_name,
                "latency_ms": round(latency_ms, 1),
                "retrieval_count": 0,
            })


def _sse(data: dict) -> str:
    """Format a dict as an SSE data line."""
    return f"data: {json.dumps(data)}\n\n"
