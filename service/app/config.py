"""Application settings loaded from environment variables.

Uses Pydantic BaseSettings so values can come from env vars, .env files,
or defaults. All settings are validated at startup — fail fast if
something critical is missing.
"""

from typing import Literal

from pydantic import model_validator
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
    retrieval_candidate_k: int = 20
    retrieval_final_k: int = 5
    rerank_enabled: bool = False
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    reranker_max_candidates: int = 30

    # Input validation
    max_query_length: int = 1000

    # Observability — empty string means logging is disabled
    bigquery_query_log_table: str = ""

    # Phase 4: Agent — empty string disables the agent (all queries → RAG)
    bigquery_metrics_dataset: str = ""
    bigquery_max_bytes_billed: int = 100_000_000

    # Phase 5: Upload + Dashboard
    gcs_uploads_bucket: str = ""
    bigquery_observability_dataset: str = ""
    max_upload_size_bytes: int = 10_485_760  # 10 MB
    allowed_upload_extensions: str = (
        "md,yaml,yml,json,txt,conf,cfg,ini,toml,dockerfile,sh,xml,csv,properties"
    )

    # Rate limiting (in-memory sliding window, per client IP)
    rate_limit_chat_per_min: int = 20
    rate_limit_upload_per_min: int = 5

    # SQL policy: "strict" requires fully-qualified table names from the
    # allowed list; "flex" allows unqualified and table-less queries (dev use)
    sql_policy_mode: Literal["strict", "flex"] = "strict"
    sql_allowed_tables: str = "uptime_events,resource_utilization,service_inventory"

    @model_validator(mode="after")
    def _validate_sql_policy(self) -> "Settings":
        """Strict SQL policy requires a non-empty table allowlist."""
        if self.retrieval_final_k <= 0:
            raise ValueError("retrieval_final_k must be greater than 0.")

        if self.retrieval_candidate_k < self.retrieval_final_k:
            raise ValueError(
                "retrieval_candidate_k must be >= retrieval_final_k."
            )

        if self.sql_policy_mode == "strict":
            tables = [t.strip() for t in self.sql_allowed_tables.split(",") if t.strip()]
            if not tables:
                raise ValueError(
                    "sql_allowed_tables must not be empty when sql_policy_mode is 'strict'. "
                    "Provide a comma-separated list of allowed table names, or set "
                    "sql_policy_mode to 'flex' for development use."
                )
        return self

    def get_allowed_tables_set(self) -> frozenset[str]:
        """Parse sql_allowed_tables into a frozenset for use by the SQL validator."""
        return frozenset(
            t.strip() for t in self.sql_allowed_tables.split(",") if t.strip()
        )

    def get_allowed_extensions_set(self) -> frozenset[str]:
        """Parse allowed_upload_extensions into a frozenset."""
        return frozenset(
            ext.strip().lower()
            for ext in self.allowed_upload_extensions.split(",")
            if ext.strip()
        )
