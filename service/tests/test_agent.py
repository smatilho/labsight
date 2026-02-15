"""Tests for the LangGraph agent."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from app.agent.graph import create_labsight_agent


@pytest.fixture
def mock_tools():
    tool1 = MagicMock()
    tool1.name = "search_documents"
    tool1.description = "Search documents"
    tool1.args_schema = None

    tool2 = MagicMock()
    tool2.name = "query_infrastructure_metrics"
    tool2.description = "Query BigQuery"
    tool2.args_schema = None

    return [tool1, tool2]


class TestCreateLabsightAgent:
    @patch("app.agent.graph.create_react_agent")
    def test_creates_agent_with_tools(
        self, mock_create: MagicMock, mock_tools: list
    ) -> None:
        mock_create.return_value = MagicMock()
        mock_llm = MagicMock()

        agent = create_labsight_agent(mock_llm, mock_tools)

        mock_create.assert_called_once()
        call_kwargs = mock_create.call_args
        assert call_kwargs.kwargs["model"] is mock_llm
        assert call_kwargs.kwargs["tools"] == mock_tools
        assert "prompt" in call_kwargs.kwargs

    @patch("app.agent.graph.create_react_agent")
    def test_system_prompt_included(
        self, mock_create: MagicMock, mock_tools: list
    ) -> None:
        mock_create.return_value = MagicMock()
        mock_llm = MagicMock()

        create_labsight_agent(mock_llm, mock_tools)

        prompt = mock_create.call_args.kwargs["prompt"]
        assert "Labsight" in prompt
        assert "BigQuery" in prompt
        assert "search_documents" in prompt or "documentation" in prompt.lower()

    @patch("app.agent.graph.create_react_agent")
    def test_returns_compiled_graph(
        self, mock_create: MagicMock, mock_tools: list
    ) -> None:
        expected_graph = MagicMock()
        mock_create.return_value = expected_graph
        mock_llm = MagicMock()

        result = create_labsight_agent(mock_llm, mock_tools)

        assert result is expected_graph

    @patch("app.agent.graph.create_react_agent")
    def test_agent_with_empty_tools(self, mock_create: MagicMock) -> None:
        mock_create.return_value = MagicMock()
        mock_llm = MagicMock()

        agent = create_labsight_agent(mock_llm, [])

        assert mock_create.call_args.kwargs["tools"] == []
