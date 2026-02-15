"""Tests for the vector retrieval tool."""

from unittest.mock import MagicMock

from langchain_core.documents import Document

from app.agent.tools.vector_retrieval import create_retrieval_tool


class TestVectorRetrievalTool:
    def test_returns_success_with_documents(self) -> None:
        mock_retriever = MagicMock()
        mock_retriever.invoke.return_value = [
            Document(
                page_content="AdGuard runs on CT 102",
                metadata={"source": "dns.md", "similarity_score": 0.85},
            ),
        ]

        tool_fn = create_retrieval_tool(mock_retriever)
        result = tool_fn.invoke("How is AdGuard configured?")

        assert result["ok"] is True
        assert len(result["data"]) == 1
        assert result["data"][0]["source"] == "dns.md"
        assert result["data"][0]["score"] == 0.85

    def test_returns_empty_data_when_no_documents(self) -> None:
        mock_retriever = MagicMock()
        mock_retriever.invoke.return_value = []

        tool_fn = create_retrieval_tool(mock_retriever)
        result = tool_fn.invoke("nonexistent topic")

        assert result["ok"] is True
        assert result["data"] == []

    def test_returns_error_on_retriever_failure(self) -> None:
        mock_retriever = MagicMock()
        mock_retriever.invoke.side_effect = ConnectionError("ChromaDB unreachable")

        tool_fn = create_retrieval_tool(mock_retriever)
        result = tool_fn.invoke("test query")

        assert result["ok"] is False
        assert "ChromaDB unreachable" in result["error"]
        assert result["data"] is None

    def test_multiple_documents(self) -> None:
        mock_retriever = MagicMock()
        mock_retriever.invoke.return_value = [
            Document(page_content="doc1", metadata={"source": "a.md", "similarity_score": 0.9}),
            Document(page_content="doc2", metadata={"source": "b.md", "similarity_score": 0.7}),
        ]

        tool_fn = create_retrieval_tool(mock_retriever)
        result = tool_fn.invoke("test")

        assert result["ok"] is True
        assert len(result["data"]) == 2

    def test_missing_metadata_defaults(self) -> None:
        mock_retriever = MagicMock()
        mock_retriever.invoke.return_value = [
            Document(page_content="content", metadata={}),
        ]

        tool_fn = create_retrieval_tool(mock_retriever)
        result = tool_fn.invoke("test")

        assert result["ok"] is True
        assert result["data"][0]["source"] == "unknown"
        assert result["data"][0]["score"] == 0.0
