"""Tests for Phase 6 reranker implementations."""

from __future__ import annotations

from langchain_core.documents import Document

from app.rag.reranker import CrossEncoderReranker, NoOpReranker


class TestNoOpReranker:
    def test_preserves_order_and_adds_rank_metadata(self) -> None:
        docs = [
            Document(page_content="doc1", metadata={"similarity_score": 0.9}),
            Document(page_content="doc2", metadata={"similarity_score": 0.6}),
        ]

        reranker = NoOpReranker()
        out = reranker.rerank("query", docs, top_k=2)

        assert [d.page_content for d in out] == ["doc1", "doc2"]
        assert out[0].metadata["retrieval_rank"] == 1
        assert out[0].metadata["rerank_rank"] == 1
        assert out[1].metadata["retrieval_rank"] == 2
        assert out[1].metadata["rerank_rank"] == 2


class TestCrossEncoderReranker:
    def test_reorders_by_cross_encoder_score(self) -> None:
        docs = [
            Document(page_content="lower score", metadata={}),
            Document(page_content="higher score", metadata={}),
        ]

        reranker = CrossEncoderReranker(
            model_name="cross-encoder/ms-marco-MiniLM-L-6-v2"
        )
        reranker._get_model = lambda: type(
            "FakeModel", (), {"predict": staticmethod(lambda pairs: [0.2, 0.9])}
        )()

        out = reranker.rerank("query", docs, top_k=2)
        assert [d.page_content for d in out] == ["higher score", "lower score"]
        assert out[0].metadata["retrieval_rank"] == 2
        assert out[0].metadata["rerank_rank"] == 1

    def test_respects_top_k(self) -> None:
        docs = [
            Document(page_content=f"doc{i}", metadata={})
            for i in range(1, 6)
        ]
        reranker = CrossEncoderReranker(
            model_name="cross-encoder/ms-marco-MiniLM-L-6-v2",
            max_candidates=5,
        )
        reranker._get_model = lambda: type(
            "FakeModel", (), {"predict": staticmethod(lambda pairs: [0.1, 0.2, 0.3, 0.4, 0.5])}
        )()

        out = reranker.rerank("query", docs, top_k=3)
        assert len(out) == 3
        assert [d.page_content for d in out] == ["doc5", "doc4", "doc3"]
