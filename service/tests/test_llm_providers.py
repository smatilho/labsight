"""Tests for LLM provider abstraction and factory."""

from unittest.mock import patch

import pytest

from app.config import Settings
from app.llm.provider import LLMProvider, create_provider


@pytest.fixture
def vertex_settings(settings: Settings) -> Settings:
    settings.llm_provider = "vertex_ai"
    return settings


@pytest.fixture
def openrouter_settings(settings: Settings) -> Settings:
    settings.llm_provider = "openrouter"
    return settings


class TestCreateProvider:
    def test_invalid_provider_raises(self, settings: Settings) -> None:
        settings.llm_provider = "nonexistent"
        with pytest.raises(ValueError, match="Unknown LLM provider"):
            create_provider(settings)

    @patch("app.llm.vertex_ai.ChatVertexAI")
    def test_vertex_ai_factory(
        self, mock_chat: object, vertex_settings: Settings
    ) -> None:
        provider = create_provider(vertex_settings)
        assert isinstance(provider, LLMProvider)
        assert "vertex_ai" in provider.get_model_name()

    @patch("app.llm.openrouter.ChatOpenAI")
    def test_openrouter_factory(
        self, mock_chat: object, openrouter_settings: Settings
    ) -> None:
        provider = create_provider(openrouter_settings)
        assert isinstance(provider, LLMProvider)
        assert "openrouter" in provider.get_model_name()


class TestVertexAIProvider:
    @patch("app.llm.vertex_ai.ChatVertexAI")
    def test_get_chat_model(
        self, mock_cls: object, vertex_settings: Settings
    ) -> None:
        provider = create_provider(vertex_settings)
        model = provider.get_chat_model()
        assert model is not None

    def test_get_model_name(self, vertex_settings: Settings) -> None:
        provider = create_provider(vertex_settings)
        assert provider.get_model_name() == "vertex_ai/gemini-2.0-flash"


class TestOpenRouterProvider:
    @patch("app.llm.openrouter.ChatOpenAI")
    def test_get_chat_model(
        self, mock_cls: object, openrouter_settings: Settings
    ) -> None:
        provider = create_provider(openrouter_settings)
        model = provider.get_chat_model()
        assert model is not None

    def test_get_model_name(self, openrouter_settings: Settings) -> None:
        provider = create_provider(openrouter_settings)
        name = provider.get_model_name()
        assert "openrouter" in name
        assert "claude" in name
