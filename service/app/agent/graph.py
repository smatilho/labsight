"""LangGraph ReAct agent for hybrid queries.

Uses ``create_react_agent`` from langgraph.prebuilt — simpler than a custom
StateGraph, and the ReAct loop is sufficient for a 2-tool agent (document
search + BigQuery SQL).

The agent is created once at startup and invoked per request. Tool factories
capture runtime config so the agent graph stays stateless.
"""

from __future__ import annotations

from typing import Any

from langchain_core.language_models import BaseChatModel
from langgraph.prebuilt import create_react_agent

_SYSTEM_PROMPT = """\
You are Labsight, an AI operations assistant for a self-hosted homelab \
infrastructure. You have access to tools for searching documentation and \
querying infrastructure metrics in BigQuery.

Rules:
1. When answering questions about metrics (uptime, CPU, memory, etc.), \
use the query_infrastructure_metrics tool to query BigQuery.
2. When answering questions about configuration, setup, or documentation, \
use the search_documents tool.
3. For hybrid questions that need both metrics and documentation, use both tools.
4. Always cite your sources — reference the tool results that support your answer.
5. Write valid BigQuery SQL. Use fully-qualified table names.
6. If a tool returns an error, explain what went wrong and try a different approach.
7. Redacted values like [PRIVATE_IP_1] are intentional — do not try to guess \
the original values.
8. Keep answers concise and technical.
"""


def create_labsight_agent(
    llm: BaseChatModel,
    tools: list[Any],
) -> Any:
    """Build and compile the Labsight ReAct agent.

    Returns a compiled LangGraph graph that can be invoked with
    ``agent.ainvoke({"messages": [...]})`` or streamed with
    ``agent.astream_events(...)``.
    """
    return create_react_agent(
        model=llm,
        tools=tools,
        prompt=_SYSTEM_PROMPT,
    )
