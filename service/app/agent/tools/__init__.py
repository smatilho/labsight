"""Agent tools for the Labsight platform."""

from typing import Any, TypedDict


class ToolResult(TypedDict):
    """Structured return type shared by all agent tools.

    Agents see typed responses — they can branch on ``ok`` to decide
    whether to retry with corrected input or report the error to the user.
    """

    ok: bool
    error: str | None
    data: list[dict[str, Any]] | None
