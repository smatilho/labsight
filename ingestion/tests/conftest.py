"""Shared fixtures for ingestion tests."""

import sys
from pathlib import Path

import pytest

# Ensure the ingestion package is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture
def markdown_fixture() -> str:
    return (FIXTURES_DIR / "test-doc.md").read_text()


@pytest.fixture
def compose_fixture() -> str:
    return (FIXTURES_DIR / "test-compose.yaml").read_text()
