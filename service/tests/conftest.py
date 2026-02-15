"""Shared test fixtures for the RAG service.

chromadb 1.5.0 uses Pydantic V1 which breaks on Python 3.14. We inject
a mock chromadb module into sys.modules so tests never touch the real
package. Production runs Python 3.12 in Docker where this isn't an issue.
"""

import sys
import types
from unittest.mock import MagicMock

import pytest

# Inject a stub 'chromadb' into sys.modules BEFORE anything imports it.
# This prevents the Pydantic V1 crash on Python 3.14.
if "chromadb" not in sys.modules:
    _mock_chromadb = types.ModuleType("chromadb")
    _mock_chromadb.HttpClient = MagicMock  # type: ignore[attr-defined]
    sys.modules["chromadb"] = _mock_chromadb

from app.config import Settings


@pytest.fixture
def settings() -> Settings:
    """Minimal settings for unit tests — no real GCP calls."""
    return Settings(
        gcp_project="test-project",
        gcp_region="us-east1",
        chromadb_url="https://chromadb-test.run.app",
        llm_provider="vertex_ai",
        openrouter_api_key="test-key",
        bigquery_query_log_table="",
    )
