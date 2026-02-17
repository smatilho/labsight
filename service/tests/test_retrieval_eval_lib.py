"""Unit tests for Phase 6 retrieval evaluation helpers."""

from pathlib import Path
from unittest.mock import patch

import pytest

import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from retrieval_eval_lib import (  # noqa: E402
    build_reranker,
    load_golden_queries,
    _first_relevant_rank,
    _percentile,
)


class TestPercentile:
    def test_percentile_handles_empty(self) -> None:
        assert _percentile([], 95) == 0.0

    def test_percentile_returns_expected_ranked_value(self) -> None:
        values = [5.0, 1.0, 3.0, 2.0, 4.0]
        assert _percentile(values, 50) == 3.0
        assert _percentile(values, 95) == 5.0


class TestRankMatching:
    def test_first_relevant_rank_supports_substring_match(self) -> None:
        top_sources = ["doc-a.md", "monitoring-notifications-dashboard-homelab.md", "doc-c.md"]
        expected = ["monitoring-notifications-dashboard-homelab"]
        assert _first_relevant_rank(top_sources, expected) == 2

    def test_first_relevant_rank_returns_none_when_missing(self) -> None:
        assert _first_relevant_rank(["a.md", "b.md"], ["missing"]) is None


class TestGoldenLoading:
    def test_load_golden_queries(self, tmp_path: Path) -> None:
        file_path = tmp_path / "golden.json"
        file_path.write_text(
            '[{"query":"What is monitoring?","expected_sources":["monitoring"]}]'
        )
        loaded = load_golden_queries(file_path)
        assert len(loaded) == 1
        assert loaded[0].query == "What is monitoring?"
        assert loaded[0].expected_sources == ["monitoring"]


class TestBuildReranker:
    def test_invalid_mode_rejected(self) -> None:
        with pytest.raises(ValueError, match="reranker mode"):
            build_reranker(
                mode="invalid",
                model_name="cross-encoder/ms-marco-MiniLM-L-6-v2",
                max_candidates=30,
                fail_on_error=False,
            )

    def test_cross_encoder_falls_back_to_noop_when_unavailable(self) -> None:
        with patch(
            "retrieval_eval_lib.CrossEncoderReranker.ensure_ready",
            side_effect=RuntimeError("missing dependency"),
        ):
            reranker, effective_mode, notes = build_reranker(
                mode="cross_encoder",
                model_name="cross-encoder/ms-marco-MiniLM-L-6-v2",
                max_candidates=30,
                fail_on_error=False,
            )
        assert reranker.__class__.__name__ == "NoOpReranker"
        assert effective_mode == "noop"
        assert notes
