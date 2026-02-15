"""BigQuery SQL tool for the LangGraph agent.

Generates and executes read-only SQL queries against the infrastructure_metrics
dataset. Uses sqlglot to parse and validate SQL at the AST level — stronger
than keyword regex against injection, case tricks, and comment-based attacks.

Safety layers (defense-in-depth; IAM dataViewer is the primary enforcement):
  1. sqlglot parse → reject invalid SQL
  2. Single-statement enforcement
  3. SELECT-only allowlist (walks subqueries too)
  4. Blocked functions: EXTERNAL_QUERY, ML.*, and other TVFs
  5. Blocked metadata: INFORMATION_SCHEMA references
  6. Table allowlist: only the configured project.dataset.table (strict mode)
     or project.dataset (flex mode, allows unqualified tables)
  7. Strict mode: requires fully-qualified table refs + named table allowlist
  8. Auto-appended LIMIT 1000
  9. QueryJobConfig: 100MB bytes_billed cap, 30s timeout
  10. Response payload capped at 50KB
"""

from __future__ import annotations

import json
import logging
from typing import Any

import sqlglot
from langchain_core.tools import tool
from sqlglot import exp

from app.agent.tools import ToolResult

logger = logging.getLogger(__name__)

_MAX_RESULT_BYTES = 50_000  # 50KB response cap
_DEFAULT_LIMIT = 1000

# Functions that can access external data sources or bypass the table allowlist.
# Checked against all function calls in the AST (Anonymous + typed Func nodes).
# Note: IAM is the primary enforcement layer — the RAG service account has
# roles/bigquery.dataViewer scoped to the infrastructure_metrics dataset only.
# This blocklist is defense-in-depth against the LLM generating queries that
# reference external connections or ML endpoints.
_BLOCKED_FUNCTIONS: frozenset[str] = frozenset({
    "external_query",
    "read_gbq",
    "ml.predict",
    "ml.evaluate",
    "ml.generate_text",
    "ml.forecast",
    "ml.recommend",
    "ml.detect_anomalies",
})


def _normalize_function_token(name: str) -> str:
    """Normalize function names for consistent blocklist matching."""
    return (
        name.strip()
        .lower()
        .replace(".", "")
        .replace("_", "")
        .replace(" ", "")
    )


_BLOCKED_FUNCTIONS_CANONICAL = frozenset(
    _normalize_function_token(name) for name in _BLOCKED_FUNCTIONS
)
_BLOCKED_FUNCTION_BASENAME_DISPLAY = {
    _normalize_function_token(name.split(".", 1)[1]): name.upper()
    for name in _BLOCKED_FUNCTIONS
    if "." in name
}


def _blocked_function_label(func: exp.Func) -> str | None:
    """Return the blocked function name for an AST node, if blocked."""
    candidates: list[str] = []

    if isinstance(func, exp.Anonymous) and func.name:
        candidates.append(func.name)

    sql_name = func.sql_name()
    if sql_name:
        candidates.append(sql_name)

    candidates.append(type(func).__name__)

    for candidate in candidates:
        normalized = _normalize_function_token(candidate)
        if normalized in _BLOCKED_FUNCTIONS_CANONICAL:
            return candidate.upper()
        mapped = _BLOCKED_FUNCTION_BASENAME_DISPLAY.get(normalized)
        if mapped:
            return mapped

    return None

# Table schemas embedded in the tool docstring so the LLM knows
# exact columns. Updated when tables change.
_TABLE_SCHEMAS = """\
Tables in the infrastructure_metrics dataset:

1. uptime_events (partitioned by checked_at)
   - checked_at: TIMESTAMP (required)
   - service_name: STRING (required)
   - status: STRING (required) — "up" or "down"
   - response_time_ms: FLOAT
   - status_code: INTEGER
   - message: STRING

2. resource_utilization (partitioned by collected_at)
   - collected_at: TIMESTAMP (required)
   - node: STRING (required)
   - cpu_percent: FLOAT
   - memory_percent: FLOAT
   - storage_percent: FLOAT

3. service_inventory
   - service_name: STRING (required)
   - host: STRING
   - port: INTEGER
   - container_type: STRING — "lxc" or "docker"
   - last_seen: TIMESTAMP
"""


class SQLValidationError(Exception):
    """Raised when SQL fails validation."""


def validate_sql(
    sql: str,
    allowed_project: str,
    allowed_dataset: str,
    *,
    policy_mode: str = "strict",
    allowed_tables: frozenset[str] | None = None,
) -> str:
    """Parse, validate, and normalize a SQL string. Returns cleaned SQL.

    Policy modes:
      - strict: requires fully-qualified table names from the allowed list,
        rejects table-less queries and unqualified references.
      - flex: allows unqualified tables and table-less queries (dev use).
        Project/dataset checks still enforced when qualifiers are present.

    Raises SQLValidationError on any validation failure.
    """
    # 0. Validate policy_mode (defense-in-depth — config.py enforces via Literal,
    # but this catches direct callers that bypass Settings)
    if policy_mode not in ("strict", "flex"):
        raise SQLValidationError(
            f"Unknown sql_policy_mode '{policy_mode}'. Must be 'strict' or 'flex'."
        )

    if policy_mode == "strict" and not allowed_tables:
        raise SQLValidationError(
            "Strict mode requires a non-empty allowed_tables set."
        )

    # 1. Parse
    try:
        statements = sqlglot.parse(sql, dialect="bigquery")
    except sqlglot.errors.ParseError as e:
        raise SQLValidationError(f"SQL parse error: {e}") from e

    # Filter out None entries (empty statements from trailing semicolons)
    statements = [s for s in statements if s is not None]

    # 2. Single statement
    if len(statements) != 1:
        raise SQLValidationError(
            f"Only single SQL statements are allowed. Got {len(statements)} statements."
        )

    statement = statements[0]

    # 3. SELECT only at top level
    if not isinstance(statement, exp.Select):
        stmt_type = type(statement).__name__
        raise SQLValidationError(
            f"Only SELECT statements are allowed. Got: {stmt_type}"
        )

    # 4. Walk all subqueries — reject non-SELECT
    for node in statement.walk():
        if isinstance(node, (exp.Insert, exp.Update, exp.Delete, exp.Drop,
                             exp.Create, exp.Alter, exp.Command)):
            raise SQLValidationError(
                f"Only SELECT statements are allowed. Found disallowed: {type(node).__name__}"
            )

    # 5. Block dangerous functions (table-valued functions that bypass table allowlist).
    # Handles both Anonymous nodes (e.g. EXTERNAL_QUERY) and typed Func nodes
    # (e.g. ML.PREDICT parsed as Predict).
    for func in statement.find_all(exp.Func):
        blocked_name = _blocked_function_label(func)
        if blocked_name:
            raise SQLValidationError(
                f"Function '{blocked_name}' is not allowed."
            )

    # Collect CTE alias names so they're excluded from table validation.
    # CTEs define temporary named result sets — they aren't real tables.
    cte_aliases: set[str] = set()
    for cte in statement.find_all(exp.CTE):
        if cte.alias:
            cte_aliases.add(cte.alias.lower())

    # 6. Table allowlist
    allowed_project_lower = allowed_project.lower()
    allowed_dataset_lower = allowed_dataset.lower()
    allowed_tables_lower = (
        frozenset(t.lower() for t in allowed_tables) if allowed_tables else frozenset()
    )
    is_strict = policy_mode == "strict"

    real_table_count = 0

    for table in statement.find_all(exp.Table):
        table_name = (table.name or "").lower()
        table_catalog = (table.catalog or "").lower()
        table_db = (table.db or "").lower()

        # Skip CTE aliases — they aren't real tables
        if table_name in cte_aliases and not table_catalog and not table_db:
            continue

        # Block INFORMATION_SCHEMA — metadata views outside the allowed dataset
        if "information_schema" in table_name or "information_schema" in table_db:
            raise SQLValidationError(
                "INFORMATION_SCHEMA queries are not allowed."
            )

        # Fully qualified: project.dataset.table
        if table_catalog and table_catalog != allowed_project_lower:
            raise SQLValidationError(
                f"Query references project '{table.catalog}' — "
                f"only '{allowed_project}' is allowed."
            )
        if table_db and table_db != allowed_dataset_lower:
            raise SQLValidationError(
                f"Query references dataset '{table.db}' — "
                f"only '{allowed_dataset}' is allowed."
            )

        # Strict mode: require fully-qualified references and validate table name
        if is_strict:
            if not table_catalog or not table_db:
                raise SQLValidationError(
                    f"Table '{table.name}' must be fully qualified as "
                    f"'{allowed_project}.{allowed_dataset}.{table.name}' in strict mode."
                )
            if table_name not in allowed_tables_lower:
                raise SQLValidationError(
                    f"Table '{table.name}' is not in the allowed table list."
                )

        real_table_count += 1

    # Strict mode: require at least one real table reference
    if is_strict and real_table_count == 0:
        raise SQLValidationError(
            "Query must reference at least one table in strict mode."
        )

    # 7. Auto-append LIMIT if missing
    if not statement.find(exp.Limit):
        statement = statement.limit(_DEFAULT_LIMIT)

    return statement.sql(dialect="bigquery")


def create_bigquery_tool(
    project_id: str,
    dataset_id: str,
    max_bytes_billed: int = 100_000_000,
    policy_mode: str = "strict",
    allowed_tables: frozenset[str] | None = None,
) -> Any:
    """Factory: returns a LangChain @tool that executes validated BigQuery SQL.

    The closure captures project_id, dataset_id, and safety settings so
    the tool function has the simple (sql: str) -> ToolResult signature
    that LangGraph expects.
    """

    docstring = (
        f"Execute a read-only BigQuery SQL query against the homelab infrastructure metrics.\n\n"
        f"Write standard BigQuery SQL. Only SELECT statements are allowed.\n"
        f"Tables are in the `{project_id}.{dataset_id}` dataset.\n\n"
        f"{_TABLE_SCHEMAS}\n"
        f"Tips:\n"
        f"- Use fully-qualified table names: `{project_id}.{dataset_id}.table_name`\n"
        f"- Partitioned tables (uptime_events, resource_utilization) are most efficient\n"
        f"  when you filter on the partition column (checked_at / collected_at).\n"
        f"- A LIMIT of 1000 is auto-appended if you don't specify one."
    )

    @tool(description=docstring)
    def query_infrastructure_metrics(sql: str) -> ToolResult:
        """Execute a read-only BigQuery SQL query."""
        # Validate
        try:
            cleaned_sql = validate_sql(
                sql, project_id, dataset_id,
                policy_mode=policy_mode,
                allowed_tables=allowed_tables,
            )
        except SQLValidationError as e:
            return ToolResult(ok=False, error=str(e), data=None)

        # Execute
        try:
            from google.cloud import bigquery

            bq_client = bigquery.Client(project=project_id)
            job_config = bigquery.QueryJobConfig(
                maximum_bytes_billed=max_bytes_billed,
                default_dataset=f"{project_id}.{dataset_id}",
            )

            query_job = bq_client.query(cleaned_sql, job_config=job_config)
            rows = list(query_job.result(timeout=30))

            # Serialize rows
            data = [dict(row) for row in rows]

            # Truncate response payload
            payload = json.dumps(data, default=str)
            if len(payload) > _MAX_RESULT_BYTES:
                # Re-serialize with truncated rows
                truncated: list[dict[str, Any]] = []
                running_size = 2  # for "[]"
                for row in data:
                    row_json = json.dumps(row, default=str)
                    if running_size + len(row_json) + 1 > _MAX_RESULT_BYTES:
                        break
                    truncated.append(row)
                    running_size += len(row_json) + 1
                data = truncated

            return ToolResult(ok=True, error=None, data=data)

        except Exception as e:
            logger.exception("BigQuery query failed")
            return ToolResult(ok=False, error=str(e), data=None)

    return query_infrastructure_metrics
