"""Tests for the heuristic query router."""

import pytest

from app.agent.router import QueryClassification, classify_query


class TestClassifyQuery:
    """Query classification with confidence scoring and fallback."""

    # --- Clear RAG queries ---

    @pytest.mark.parametrize(
        "query",
        [
            "How did I configure DNS rewrite rules?",
            "How do I set up WireGuard?",
            "Where is the Dockerfile for the ingestion service?",
            "What is the YAML config for Proxmox?",
        ],
    )
    def test_rag_classification(self, query: str) -> None:
        result = classify_query(query)
        assert result.mode == "rag", f"Expected rag for: {query!r}, got {result}"
        assert result.confidence > 0

    def test_docker_compose_with_service_name_is_hybrid(self) -> None:
        """docker-compose + Uptime triggers both RAG and metrics signals."""
        result = classify_query("What's in my docker-compose for Uptime Kuma?")
        assert result.mode == "hybrid"

    # --- Clear metrics queries ---

    @pytest.mark.parametrize(
        "query",
        [
            "Which service had the most downtime last week?",
            "Show me CPU usage for pve01 yesterday",
            "How many outages were there in the past month?",
        ],
    )
    def test_metrics_classification(self, query: str) -> None:
        result = classify_query(query)
        assert result.mode == "metrics", f"Expected metrics for: {query!r}, got {result}"
        assert result.confidence >= 0.4

    @pytest.mark.parametrize(
        "query",
        [
            "What is the average response time across all services?",
            "What is the current uptime for AdGuard?",
        ],
    )
    def test_metrics_with_what_is_triggers_hybrid(self, query: str) -> None:
        """'What is the...' + metrics keywords → hybrid (both signals fire)."""
        result = classify_query(query)
        assert result.mode == "hybrid", f"Expected hybrid for: {query!r}, got {result}"

    # --- Hybrid queries ---

    @pytest.mark.parametrize(
        "query",
        [
            "How is AdGuard configured and what's its current uptime?",
            "Is Proxmox using too much memory based on the docs?",
        ],
    )
    def test_hybrid_classification(self, query: str) -> None:
        result = classify_query(query)
        assert result.mode == "hybrid", f"Expected hybrid for: {query!r}, got {result}"

    def test_going_down_without_rag_signal_is_metrics(self) -> None:
        """'going down' is a metrics signal; no RAG signal → metrics."""
        result = classify_query("Why does Nginx keep going down?")
        assert result.mode == "metrics"

    # --- Low-confidence / fallback ---

    def test_ambiguous_no_metrics_signal_falls_back_to_rag(self) -> None:
        result = classify_query("Tell me about my homelab")
        assert result.mode == "rag"
        assert result.confidence < 0.4

    def test_ambiguous_with_metrics_signal(self) -> None:
        # "today" is a metrics signal, "What" partially matches RAG
        result = classify_query("What happened today?")
        # Both or only metrics signals fire — either metrics or hybrid is acceptable
        assert result.mode in ("metrics", "hybrid")

    # --- Confidence values ---

    def test_clear_rag_has_high_confidence(self) -> None:
        result = classify_query("How did I configure the DNS rewrite rules?")
        assert result.confidence >= 0.4

    def test_clear_metrics_has_high_confidence(self) -> None:
        result = classify_query("Which service had the most downtime last week?")
        assert result.confidence >= 0.4

    # --- Edge cases ---

    def test_empty_query_defaults_to_rag(self) -> None:
        result = classify_query("")
        assert result.mode == "rag"

    def test_returns_query_classification_dataclass(self) -> None:
        result = classify_query("test query")
        assert isinstance(result, QueryClassification)
        assert hasattr(result, "mode")
        assert hasattr(result, "confidence")

    def test_confidence_bounded_0_to_1(self) -> None:
        # Even with many signals, confidence should not exceed 1.0
        result = classify_query(
            "Show me the uptime downtime CPU memory latency "
            "response time utilization status for last week"
        )
        assert 0.0 <= result.confidence <= 1.0
