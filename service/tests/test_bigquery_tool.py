"""Tests for the BigQuery SQL tool — validation and execution."""

from unittest.mock import MagicMock, patch

import pytest

from app.agent.tools.bigquery_sql import (
    SQLValidationError,
    create_bigquery_tool,
    validate_sql,
)

PROJECT = "test-project"
DATASET = "infrastructure_metrics_dev"
ALLOWED_TABLES = frozenset({"uptime_events", "resource_utilization", "service_inventory"})


def _validate(sql: str, **kwargs) -> str:
    """Shorthand: validate with project/dataset defaults and strict mode."""
    kwargs.setdefault("policy_mode", "strict")
    kwargs.setdefault("allowed_tables", ALLOWED_TABLES)
    return validate_sql(sql, PROJECT, DATASET, **kwargs)


class TestSQLValidation:
    """SQL validation via sqlglot AST parsing (shared across both modes)."""

    def test_valid_select(self) -> None:
        sql = f"SELECT * FROM {PROJECT}.{DATASET}.uptime_events LIMIT 10"
        result = _validate(sql)
        assert "SELECT" in result

    def test_select_with_where(self) -> None:
        sql = f"SELECT service_name, status FROM {PROJECT}.{DATASET}.uptime_events WHERE status = 'down'"
        result = _validate(sql)
        assert "WHERE" in result

    def test_auto_appends_limit(self) -> None:
        sql = f"SELECT * FROM {PROJECT}.{DATASET}.uptime_events"
        result = _validate(sql)
        assert "LIMIT" in result.upper()

    def test_preserves_existing_limit(self) -> None:
        sql = f"SELECT * FROM {PROJECT}.{DATASET}.uptime_events LIMIT 5"
        result = _validate(sql)
        assert "5" in result

    def test_rejects_delete(self) -> None:
        with pytest.raises(SQLValidationError, match="SELECT"):
            _validate(f"DELETE FROM {PROJECT}.{DATASET}.uptime_events")

    def test_rejects_insert(self) -> None:
        with pytest.raises(SQLValidationError, match="SELECT"):
            _validate(
                f"INSERT INTO {PROJECT}.{DATASET}.uptime_events (service_name) VALUES ('x')",
            )

    def test_rejects_drop(self) -> None:
        with pytest.raises(SQLValidationError, match="SELECT"):
            _validate(f"DROP TABLE {PROJECT}.{DATASET}.uptime_events")

    def test_rejects_multi_statement(self) -> None:
        with pytest.raises(SQLValidationError, match="single"):
            _validate(
                f"SELECT 1; DROP TABLE {PROJECT}.{DATASET}.uptime_events",
            )

    def test_rejects_wrong_project(self) -> None:
        with pytest.raises(SQLValidationError, match="project"):
            _validate("SELECT * FROM other_project.other_dataset.table1")

    def test_rejects_wrong_dataset(self) -> None:
        with pytest.raises(SQLValidationError, match="dataset"):
            _validate(f"SELECT * FROM {PROJECT}.other_dataset.table1")

    def test_rejects_invalid_sql(self) -> None:
        with pytest.raises(SQLValidationError, match="parse"):
            _validate("NOT VALID SQL !!! %%%")

    def test_rejects_update(self) -> None:
        with pytest.raises(SQLValidationError, match="SELECT"):
            _validate(
                f"UPDATE {PROJECT}.{DATASET}.uptime_events SET status = 'up'",
            )

    def test_case_insensitive_project_check(self) -> None:
        sql = f"SELECT * FROM {PROJECT.upper()}.{DATASET.upper()}.uptime_events"
        result = _validate(sql)
        assert "uptime_events" in result.lower()

    def test_subquery_select_allowed(self) -> None:
        sql = f"SELECT * FROM (SELECT service_name FROM {PROJECT}.{DATASET}.uptime_events)"
        result = _validate(sql)
        assert "service_name" in result

    def test_rejects_external_query(self) -> None:
        sql = "SELECT * FROM EXTERNAL_QUERY('connection_id', 'SELECT 1')"
        with pytest.raises(SQLValidationError, match="EXTERNAL_QUERY"):
            _validate(sql, policy_mode="flex")

    def test_rejects_external_query_case_insensitive(self) -> None:
        sql = "SELECT * FROM external_query('conn', 'SELECT 1')"
        with pytest.raises(SQLValidationError, match="not allowed"):
            _validate(sql, policy_mode="flex")

    def test_rejects_ml_predict_typed_function(self) -> None:
        sql = (
            "SELECT * FROM ML.PREDICT("
            "MODEL test_project.infrastructure_metrics_dev.my_model, "
            "TABLE test_project.infrastructure_metrics_dev.uptime_events)"
        )
        with pytest.raises(SQLValidationError, match="ML.PREDICT"):
            _validate(sql, policy_mode="flex")

    def test_rejects_information_schema(self) -> None:
        sql = f"SELECT * FROM {PROJECT}.{DATASET}.INFORMATION_SCHEMA.TABLES"
        with pytest.raises(SQLValidationError, match="INFORMATION_SCHEMA"):
            _validate(sql)

    def test_rejects_information_schema_unqualified(self) -> None:
        sql = "SELECT * FROM INFORMATION_SCHEMA.COLUMNS"
        with pytest.raises(SQLValidationError, match="INFORMATION_SCHEMA"):
            _validate(sql, policy_mode="flex")


class TestStrictMode:
    """Strict SQL policy — fully-qualified table refs + named allowlist."""

    def test_rejects_unqualified_table(self) -> None:
        with pytest.raises(SQLValidationError, match="fully qualified"):
            _validate("SELECT * FROM uptime_events")

    def test_rejects_table_less_query(self) -> None:
        with pytest.raises(SQLValidationError, match="at least one table"):
            _validate("SELECT 1")

    def test_rejects_wrong_table_in_allowed_dataset(self) -> None:
        sql = f"SELECT * FROM {PROJECT}.{DATASET}.nonexistent_table"
        with pytest.raises(SQLValidationError, match="not in the allowed"):
            _validate(sql)

    def test_accepts_all_allowed_tables(self) -> None:
        for table in ALLOWED_TABLES:
            sql = f"SELECT * FROM {PROJECT}.{DATASET}.{table}"
            result = _validate(sql)
            assert table in result.lower()

    def test_allows_cte_with_allowed_table(self) -> None:
        sql = (
            f"WITH recent AS (SELECT * FROM {PROJECT}.{DATASET}.uptime_events "
            f"WHERE checked_at > TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 1 DAY)) "
            f"SELECT service_name, COUNT(*) FROM recent GROUP BY 1"
        )
        result = _validate(sql)
        assert "recent" in result.lower()

    def test_rejects_cte_with_disallowed_table(self) -> None:
        sql = (
            f"WITH data AS (SELECT * FROM {PROJECT}.{DATASET}.secret_table) "
            f"SELECT * FROM data"
        )
        with pytest.raises(SQLValidationError, match="not in the allowed"):
            _validate(sql)

    def test_strict_rejects_empty_allowed_tables(self) -> None:
        """Strict mode + empty allowlist is rejected at validation time."""
        sql = f"SELECT * FROM {PROJECT}.{DATASET}.uptime_events"
        with pytest.raises(SQLValidationError, match="non-empty"):
            _validate(sql, allowed_tables=frozenset())

    def test_strict_rejects_none_allowed_tables(self) -> None:
        """Strict mode + None allowlist is rejected at validation time."""
        sql = f"SELECT * FROM {PROJECT}.{DATASET}.uptime_events"
        with pytest.raises(SQLValidationError, match="non-empty"):
            _validate(sql, allowed_tables=None)


class TestPolicyModeValidation:
    """Unknown policy modes are rejected."""

    def test_rejects_unknown_policy_mode(self) -> None:
        sql = f"SELECT * FROM {PROJECT}.{DATASET}.uptime_events"
        with pytest.raises(SQLValidationError, match="Unknown sql_policy_mode"):
            _validate(sql, policy_mode="yolo")

    def test_rejects_empty_policy_mode(self) -> None:
        sql = f"SELECT * FROM {PROJECT}.{DATASET}.uptime_events"
        with pytest.raises(SQLValidationError, match="Unknown sql_policy_mode"):
            _validate(sql, policy_mode="")


class TestFlexMode:
    """Flex SQL policy — allows unqualified and table-less queries (dev use)."""

    def test_allows_unqualified_table(self) -> None:
        result = _validate("SELECT * FROM uptime_events", policy_mode="flex")
        assert "uptime_events" in result

    def test_allows_table_less_query(self) -> None:
        result = _validate("SELECT 1", policy_mode="flex")
        assert "1" in result

    def test_still_rejects_wrong_project(self) -> None:
        with pytest.raises(SQLValidationError, match="project"):
            _validate(
                "SELECT * FROM other_project.other_dataset.t", policy_mode="flex"
            )

    def test_still_rejects_wrong_dataset(self) -> None:
        with pytest.raises(SQLValidationError, match="dataset"):
            _validate(
                f"SELECT * FROM {PROJECT}.other_dataset.t", policy_mode="flex"
            )


class TestBigQueryToolExecution:
    """Tool execution with mocked BigQuery client."""

    @patch("google.cloud.bigquery.Client")
    @patch("google.cloud.bigquery.QueryJobConfig")
    def test_tool_returns_success(
        self,
        mock_job_config_cls: MagicMock,
        mock_client_cls: MagicMock,
    ) -> None:
        tool_fn = create_bigquery_tool(
            PROJECT, DATASET,
            allowed_tables=ALLOWED_TABLES,
        )

        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_job_config_cls.return_value = MagicMock()

        mock_job = MagicMock()
        mock_job.result.return_value = []
        mock_client.query.return_value = mock_job

        result = tool_fn.invoke(
            f"SELECT COUNT(*) as cnt FROM {PROJECT}.{DATASET}.uptime_events"
        )

        assert result["ok"] is True
        assert result["data"] is not None

    def test_tool_returns_validation_error(self) -> None:
        tool_fn = create_bigquery_tool(
            PROJECT, DATASET,
            allowed_tables=ALLOWED_TABLES,
        )

        result = tool_fn.invoke(f"DELETE FROM {PROJECT}.{DATASET}.uptime_events")

        assert result["ok"] is False
        assert "SELECT" in result["error"]
        assert result["data"] is None
