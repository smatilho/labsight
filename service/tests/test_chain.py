"""Tests for the RAG chain with citations."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from langchain_core.documents import Document
from langchain_core.messages import AIMessage

from app.rag.chain import RAGChain, RAGResponse, _sse


@pytest.fixture
def mock_retriever() -> MagicMock:
    retriever = MagicMock()
    retriever.invoke.return_value = [
        Document(
            page_content="AdGuard runs on CT 102 at [PRIVATE_IP_1].",
            metadata={"source": "homelab-dns.md", "similarity_score": 0.85},
        ),
        Document(
            page_content="DNS rewrites point *.lab.atilho.com to [PRIVATE_IP_2].",
            metadata={"source": "homelab-dns.md", "similarity_score": 0.72},
        ),
    ]
    return retriever


@pytest.fixture
def mock_llm() -> MagicMock:
    llm = MagicMock()
    llm.invoke.return_value = AIMessage(
        content="AdGuard runs on CT 102 [Source 1]. DNS rewrites are configured for *.lab.atilho.com [Source 2]."
    )
    return llm


@pytest.fixture
def chain(mock_retriever: MagicMock, mock_llm: MagicMock) -> RAGChain:
    return RAGChain(
        retriever=mock_retriever,
        llm=mock_llm,
        model_name="test/model",
    )


class TestRAGChainInvoke:
    def test_returns_rag_response(self, chain: RAGChain) -> None:
        result = chain.invoke("Where does AdGuard run?")

        assert isinstance(result, RAGResponse)
        assert "[Source 1]" in result.answer
        assert result.model == "test/model"
        assert result.latency_ms > 0
        assert result.retrieval_count == 2

    def test_sources_have_correct_indices(self, chain: RAGChain) -> None:
        result = chain.invoke("Where does AdGuard run?")

        assert len(result.sources) == 2
        assert result.sources[0].index == 1
        assert result.sources[1].index == 2
        assert result.sources[0].similarity_score == 0.85

    def test_empty_retrieval_returns_fallback(
        self, mock_retriever: MagicMock, mock_llm: MagicMock
    ) -> None:
        mock_retriever.invoke.return_value = []
        chain = RAGChain(
            retriever=mock_retriever,
            llm=mock_llm,
            model_name="test/model",
        )

        result = chain.invoke("something with no docs")

        assert "couldn't find" in result.answer.lower()
        assert result.sources == []
        assert result.retrieval_count == 0
        # LLM should NOT be called when there are no documents
        mock_llm.invoke.assert_not_called()


class TestRAGChainStream:
    @pytest.mark.asyncio
    async def test_stream_yields_tokens_then_sources(
        self,
        mock_retriever: MagicMock,
        mock_llm: MagicMock,
    ) -> None:
        # Set up async streaming
        chunk1 = MagicMock()
        chunk1.content = "AdGuard "
        chunk2 = MagicMock()
        chunk2.content = "runs on CT 102."

        async def fake_astream(messages):
            yield chunk1
            yield chunk2

        mock_llm.astream = fake_astream

        chain = RAGChain(
            retriever=mock_retriever,
            llm=mock_llm,
            model_name="test/model",
        )

        events = []
        async for event in chain.stream("Where does AdGuard run?"):
            events.append(event)

        # Should have: 2 tokens + 1 sources + 1 done
        assert len(events) == 4
        assert '"type": "token"' in events[0]
        assert '"type": "token"' in events[1]
        assert '"type": "sources"' in events[2]
        assert '"type": "done"' in events[3]

    @pytest.mark.asyncio
    async def test_stream_empty_retrieval(
        self,
        mock_retriever: MagicMock,
        mock_llm: MagicMock,
    ) -> None:
        mock_retriever.invoke.return_value = []

        chain = RAGChain(
            retriever=mock_retriever,
            llm=mock_llm,
            model_name="test/model",
        )

        events = []
        async for event in chain.stream("nonexistent"):
            events.append(event)

        assert len(events) == 2  # fallback token + done
        assert "couldn't find" in events[0].lower()

    @pytest.mark.asyncio
    async def test_stream_error_yields_error_and_done(
        self,
        mock_retriever: MagicMock,
        mock_llm: MagicMock,
    ) -> None:
        mock_retriever.invoke.side_effect = RuntimeError("connection refused")

        chain = RAGChain(
            retriever=mock_retriever,
            llm=mock_llm,
            model_name="test/model",
        )

        events = []
        async for event in chain.stream("will fail"):
            events.append(event)

        assert len(events) == 2
        assert '"type": "error"' in events[0]
        assert '"type": "done"' in events[1]


class TestSSEFormat:
    def test_sse_format(self) -> None:
        result = _sse({"type": "token", "content": "hello"})
        assert result.startswith("data: ")
        assert result.endswith("\n\n")
        assert '"type": "token"' in result
