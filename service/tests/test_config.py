"""Tests for application config validation — fail-fast on invalid settings."""

import pytest
from pydantic import ValidationError

from app.config import Settings

# Base kwargs for a valid Settings instance (required fields filled in)
_BASE = dict(
    gcp_project="test-project",
    chromadb_url="https://chromadb-test.run.app",
)


class TestSQLPolicyValidation:
    """SQL policy settings are validated at startup."""

    def test_invalid_policy_mode_rejected(self) -> None:
        with pytest.raises(ValidationError, match="sql_policy_mode"):
            Settings(**_BASE, sql_policy_mode="yolo")

    def test_strict_with_empty_allowed_tables_rejected(self) -> None:
        with pytest.raises(ValidationError, match="sql_allowed_tables"):
            Settings(**_BASE, sql_policy_mode="strict", sql_allowed_tables="")

    def test_strict_with_whitespace_only_allowed_tables_rejected(self) -> None:
        with pytest.raises(ValidationError, match="sql_allowed_tables"):
            Settings(**_BASE, sql_policy_mode="strict", sql_allowed_tables="  , , ")

    def test_strict_with_valid_tables_accepted(self) -> None:
        s = Settings(**_BASE, sql_policy_mode="strict", sql_allowed_tables="t1,t2")
        assert s.sql_policy_mode == "strict"
        assert s.get_allowed_tables_set() == frozenset({"t1", "t2"})

    def test_flex_with_empty_allowed_tables_accepted(self) -> None:
        s = Settings(**_BASE, sql_policy_mode="flex", sql_allowed_tables="")
        assert s.sql_policy_mode == "flex"
        assert s.get_allowed_tables_set() == frozenset()

    def test_get_allowed_tables_set_strips_whitespace(self) -> None:
        s = Settings(**_BASE, sql_allowed_tables=" t1 , t2 , t3 ")
        assert s.get_allowed_tables_set() == frozenset({"t1", "t2", "t3"})

    def test_default_policy_is_strict(self) -> None:
        s = Settings(**_BASE)
        assert s.sql_policy_mode == "strict"
        assert len(s.get_allowed_tables_set()) > 0
