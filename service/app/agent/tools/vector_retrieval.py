"""Vector retrieval tool for the LangGraph agent.

Wraps the existing ChromaDBRetriever so the agent can search homelab
documentation. Returns structured ToolResult for consistency with the
BigQuery tool.
"""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.retrievers import BaseRetriever
from langchain_core.tools import tool

from app.agent.tools import ToolResult

logger = logging.getLogger(__name__)


def create_retrieval_tool(retriever: BaseRetriever) -> Any:
    """Factory: returns a LangChain @tool that searches the document store.

    The closure captures the retriever instance so the tool has the simple
    (query: str) -> ToolResult signature that LangGraph expects.
    """

    @tool
    def search_documents(query: str) -> ToolResult:
        """Search the homelab documentation for relevant information.

        Use this tool when you need to find configuration details, setup
        instructions, architecture decisions, or other documentation about
        the homelab infrastructure. Returns the most relevant document
        chunks with similarity scores.
        """
        try:
            documents = retriever.invoke(query)

            if not documents:
                return ToolResult(
                    ok=True,
                    error=None,
                    data=[],
                )

            data = [
                {
                    "source": doc.metadata.get("source", "unknown"),
                    "content": doc.page_content,
                    "score": doc.metadata.get("similarity_score", 0.0),
                }
                for doc in documents
            ]

            return ToolResult(ok=True, error=None, data=data)

        except Exception as e:
            logger.exception("Vector retrieval failed")
            return ToolResult(ok=False, error=str(e), data=None)

    return search_documents
