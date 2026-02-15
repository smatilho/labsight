"""FastAPI application factory for the RAG service.

Initializes settings, LLM provider, retriever, and RAG chain on startup
via the lifespan context manager, stored on app.state so routers can
access them without globals.
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
        version="0.3.0",
        lifespan=lifespan,
    )
    app.include_router(health.router)
    app.include_router(chat.router)
    return app
