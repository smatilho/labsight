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
from app.middleware.rate_limit import RateLimitMiddleware
from app.rag.chain import RAGChain
from app.rag.reranker import CrossEncoderReranker, NoOpReranker
from app.rag.retriever import ChromaDBRetriever
from app.routers import chat, dashboard, health, upload

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize shared resources on startup."""
    settings = Settings()
    provider = create_provider(settings)
    retriever = ChromaDBRetriever(settings=settings)
    llm = provider.get_chat_model()
    reranker = NoOpReranker()
    if settings.rerank_enabled:
        try:
            reranker = CrossEncoderReranker(
                model_name=settings.reranker_model,
                max_candidates=settings.reranker_max_candidates,
            )
            reranker.ensure_ready()
            logger.info(
                "Reranker enabled (model=%s, max_candidates=%d)",
                settings.reranker_model,
                settings.reranker_max_candidates,
            )
        except Exception:
            logger.exception(
                "Failed to initialize cross-encoder reranker; falling back to ANN order"
            )
            reranker = NoOpReranker()
    chain = RAGChain(
        retriever=retriever,
        llm=llm,
        model_name=provider.get_model_name(),
        reranker=reranker,
        retrieval_final_k=settings.retrieval_final_k,
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
        version="0.5.0",
        lifespan=lifespan,
    )

    # Rate limiting — lightweight defense until IAP in Phase 5B
    settings = Settings()
    app.add_middleware(
        RateLimitMiddleware,
        rules={
            "/api/upload": settings.rate_limit_upload_per_min,
            "/api/chat": settings.rate_limit_chat_per_min,
        },
    )

    app.include_router(health.router)
    app.include_router(chat.router)
    app.include_router(upload.router)
    app.include_router(dashboard.router)
    return app
