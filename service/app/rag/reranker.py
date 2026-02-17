"""Document rerankers for retrieval quality tuning.

Phase 6 introduces optional reranking after ANN retrieval:
1) Vector search gets fast candidates.
2) Cross-encoder reranker re-scores candidates for relevance.
3) Top reranked docs are passed to the LLM prompt.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from langchain_core.documents import Document


class BaseReranker(ABC):
    """Interface for reranking retrieved documents."""

    @abstractmethod
    def rerank(self, query: str, docs: list[Document], top_k: int) -> list[Document]:
        """Return top_k documents ordered by relevance."""


class NoOpReranker(BaseReranker):
    """Default reranker that preserves ANN ordering."""

    def rerank(self, query: str, docs: list[Document], top_k: int) -> list[Document]:
        del query  # unused by no-op implementation
        reranked: list[Document] = []

        for retrieval_rank, doc in enumerate(docs, start=1):
            metadata = dict(doc.metadata or {})
            metadata.setdefault("retrieval_rank", retrieval_rank)
            metadata.setdefault("rerank_rank", retrieval_rank)
            metadata.setdefault(
                "rerank_score",
                float(metadata.get("similarity_score", 0.0)),
            )
            reranked.append(
                Document(page_content=doc.page_content, metadata=metadata)
            )

        return reranked[:top_k]


class CrossEncoderReranker(BaseReranker):
    """Cross-encoder reranker using sentence-transformers."""

    def __init__(self, model_name: str, max_candidates: int = 30) -> None:
        self._model_name = model_name
        self._max_candidates = max_candidates
        self._model: Any = None

    def ensure_ready(self) -> None:
        """Preload the model to validate runtime dependencies."""
        _ = self._get_model()

    def _get_model(self) -> Any:
        """Lazy-load the cross-encoder model."""
        if self._model is not None:
            return self._model

        try:
            from sentence_transformers import CrossEncoder
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "CrossEncoder reranker requires sentence-transformers. "
                "Install it in the service image or set LABSIGHT_RERANK_ENABLED=false."
            ) from exc

        self._model = CrossEncoder(self._model_name)
        return self._model

    def rerank(self, query: str, docs: list[Document], top_k: int) -> list[Document]:
        if not docs:
            return []

        limited_docs = docs[: self._max_candidates]
        pairs = [(query, doc.page_content) for doc in limited_docs]
        scores = list(self._get_model().predict(pairs))

        scored_docs: list[tuple[int, float, Document]] = []
        for retrieval_rank, (doc, score) in enumerate(zip(limited_docs, scores), start=1):
            scored_docs.append((retrieval_rank, float(score), doc))

        scored_docs.sort(key=lambda item: item[1], reverse=True)

        reranked: list[Document] = []
        for rerank_rank, (retrieval_rank, score, doc) in enumerate(scored_docs, start=1):
            metadata = dict(doc.metadata or {})
            metadata["retrieval_rank"] = retrieval_rank
            metadata["rerank_rank"] = rerank_rank
            metadata["rerank_score"] = round(score, 4)
            reranked.append(
                Document(page_content=doc.page_content, metadata=metadata)
            )

        return reranked[:top_k]
