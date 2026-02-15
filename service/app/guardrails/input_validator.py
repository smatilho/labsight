"""Input validation and basic prompt injection detection.

Applied before any LLM call to reject malformed or suspicious queries.
Raises HTTPException(400) so FastAPI returns a clean error response.
"""

import re

from fastapi import HTTPException

# Patterns that suggest prompt injection attempts. These are basic
# heuristics — Phase 7 will add more sophisticated detection.
_INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?(previous|above|prior)\s+(instructions|prompts)", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+(a|an)\s+", re.IGNORECASE),
    re.compile(r"system\s*:\s*", re.IGNORECASE),
    re.compile(r"<\s*/?\s*system\s*>", re.IGNORECASE),
]


def validate_query(query: str, max_length: int) -> str:
    """Validate and sanitize an incoming query string.

    Returns the stripped query on success.
    Raises HTTPException(400) on validation failure.
    """
    stripped = query.strip()

    if not stripped:
        raise HTTPException(status_code=400, detail="Query cannot be empty.")

    if len(stripped) > max_length:
        raise HTTPException(
            status_code=400,
            detail=f"Query exceeds maximum length of {max_length} characters.",
        )

    for pattern in _INJECTION_PATTERNS:
        if pattern.search(stripped):
            raise HTTPException(
                status_code=400,
                detail="Query rejected by input validation.",
            )

    return stripped
