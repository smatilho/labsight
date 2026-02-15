"""Application settings loaded from environment variables.

Uses Pydantic BaseSettings so values can come from env vars, .env files,
or defaults. All settings are validated at startup — fail fast if
something critical is missing.
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """RAG service configuration."""

    model_config = {"env_prefix": "LABSIGHT_"}

    # GCP
    gcp_project: str
    gcp_region: str = "us-east1"

    # ChromaDB (Cloud Run service from Phase 2)
    chromadb_url: str
    chromadb_collection: str = "labsight_docs"

    # LLM provider: "vertex_ai" or "openrouter"
    llm_provider: str = "vertex_ai"

    # Vertex AI (Gemini)
    vertex_model: str = "gemini-2.0-flash"

    # OpenRouter (Claude via OpenAI-compatible API)
    openrouter_api_key: str = ""
    openrouter_model: str = "anthropic/claude-sonnet-4-20250514"

    # RAG tuning
    retrieval_top_k: int = 5

    # Input validation
    max_query_length: int = 1000

    # Observability — empty string means logging is disabled
    bigquery_query_log_table: str = ""
