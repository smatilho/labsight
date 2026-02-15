"""FastAPI application factory for the RAG service.

Initializes settings, LLM provider, retriever, and RAG chain on startup
via the lifespan context manager, stored on app.state so routers can
access them without globals.

Phase 4 adds a LangGraph agent for metrics/hybrid queries. The agent is
only created when LABSIGHT_BIGQUERY_METRICS_DATASET is configured —
otherwise all queries fall back to the RAG chain.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import Settings
from app.llm.provider import create_provider
from app.rag.chain import RAGChain
from app.rag.retriever import ChromaDBRetriever
from app.routers import chat, health

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize shared resources on startup."""
    settings = Settings()
    provider = create_provider(settings)
    retriever = ChromaDBRetriever(settings=settings)
    llm = provider.get_chat_model()
    chain = RAGChain(
        retriever=retriever,
        llm=llm,
        model_name=provider.get_model_name(),
    )

    app.state.settings = settings
    app.state.provider = provider
    app.state.retriever = retriever
    app.state.chain = chain

    # Phase 4: Create agent if metrics dataset is configured
    agent = None
    if settings.bigquery_metrics_dataset:
        from app.agent.graph import create_labsight_agent
        from app.agent.tools.bigquery_sql import create_bigquery_tool
        from app.agent.tools.vector_retrieval import create_retrieval_tool

        bq_tool = create_bigquery_tool(
            project_id=settings.gcp_project,
            dataset_id=settings.bigquery_metrics_dataset,
            max_bytes_billed=settings.bigquery_max_bytes_billed,
            policy_mode=settings.sql_policy_mode,
            allowed_tables=settings.get_allowed_tables_set(),
        )
        retrieval_tool = create_retrieval_tool(retriever)
        agent = create_labsight_agent(llm, [bq_tool, retrieval_tool])

        logger.info(
            "Agent ready (dataset=%s)", settings.bigquery_metrics_dataset
        )
    else:
        logger.info("Agent disabled — LABSIGHT_BIGQUERY_METRICS_DATASET not set")

    app.state.agent = agent

    logger.info(
        "Labsight RAG service ready (model=%s, chromadb=%s)",
        provider.get_model_name(),
        settings.chromadb_url,
    )
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="Labsight RAG Service",
        description="AI-powered operations assistant for homelab infrastructure",
        version="0.4.0",
        lifespan=lifespan,
    )
    app.include_router(health.router)
    app.include_router(chat.router)
    return app
