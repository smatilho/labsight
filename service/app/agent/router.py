"""Heuristic query router — classifies queries as rag, metrics, or hybrid.

No LLM call: ~1ms, deterministic, free, easily testable. Two keyword/pattern
sets are scored against the query. Confidence reflects how many signals
matched and how strongly.

Fallback rules prevent silent misrouting:
  - Low confidence + metrics signal → hybrid (safest)
  - Low confidence + no metrics signal → rag (don't spin up the agent)
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_CONFIDENCE_THRESHOLD = 0.4

# --- Signal definitions ---
# (pattern, weight) — exact keywords get 1.0, partial/substring gets 0.5

_METRICS_SIGNALS: list[tuple[re.Pattern[str], float]] = [
    # Direct metric keywords
    (re.compile(r"\b(uptime|downtime|outage)\b", re.I), 1.0),
    (re.compile(r"\bcpu\b", re.I), 1.0),
    (re.compile(r"\bmemory\b", re.I), 0.8),
    (re.compile(r"\b(disk|storage)\s*(usage|utilization|percent)?\b", re.I), 0.8),
    (re.compile(r"\blatency\b", re.I), 1.0),
    (re.compile(r"\bresponse\s*time\b", re.I), 1.0),
    (re.compile(r"\bavailability\b", re.I), 0.8),
    (re.compile(r"\butilization\b", re.I), 0.8),
    (re.compile(r"\bservice\s*status\b", re.I), 0.8),
    (re.compile(r"\bstatus\s*code\b", re.I), 0.8),
    # Temporal patterns (strongly suggest metrics queries)
    (re.compile(r"\b(last|past)\s+(week|month|day|hour|24\s*hours?)\b", re.I), 0.8),
    (re.compile(r"\byesterday\b", re.I), 0.7),
    (re.compile(r"\btoday\b", re.I), 0.5),
    (re.compile(r"\brecent(ly)?\b", re.I), 0.5),
    # Aggregation patterns
    (re.compile(r"\bhow\s+many\b", re.I), 0.6),
    (re.compile(r"\bwhich\s+service\b", re.I), 0.7),
    (re.compile(r"\b(most|worst|best|average|avg|total|count)\b", re.I), 0.6),
    # Verbs suggesting data analysis
    (re.compile(r"\b(show|list|display)\s+me\b", re.I), 0.4),
    (re.compile(r"\btrend\b", re.I), 0.7),
    (re.compile(r"\b(go(ing|es|ne)?\s+)?down\b", re.I), 0.5),
]

_RAG_SIGNALS: list[tuple[re.Pattern[str], float]] = [
    (re.compile(r"\bconfigur(e|ed|ation)\b", re.I), 1.0),
    (re.compile(r"\bconfig\b", re.I), 0.8),
    (re.compile(r"\bsetup\b", re.I), 0.8),
    (re.compile(r"\bset\s+up\b", re.I), 0.8),
    (re.compile(r"\binstall(ed|ation)?\b", re.I), 0.8),
    (re.compile(r"\bdocs?\b", re.I), 0.8),
    (re.compile(r"\bdocument(ation|s)?\b", re.I), 1.0),
    (re.compile(r"\bhow\s+do\s+I\b", re.I), 0.9),
    (re.compile(r"\bhow\s+did\s+I\b", re.I), 1.0),
    (re.compile(r"\bwhat\s+is\s+the\b", re.I), 0.5),
    (re.compile(r"\bwhere\s+is\b", re.I), 0.6),
    (re.compile(r"\bdocker[-\s]?compose\b", re.I), 1.0),
    (re.compile(r"\bdns\s*rewrite\b", re.I), 1.0),
    (re.compile(r"\byaml\b", re.I), 0.7),
    (re.compile(r"\bdockerfile\b", re.I), 0.8),
    (re.compile(r"\bwhat\s+port\b", re.I), 0.7),
    (re.compile(r"\bwhat\s+IP\b", re.I), 0.7),
]


@dataclass(frozen=True, slots=True)
class QueryClassification:
    """Result of query classification with confidence score."""

    mode: str  # "rag", "metrics", or "hybrid"
    confidence: float  # 0.0 – 1.0


def _score(query: str, signals: list[tuple[re.Pattern[str], float]]) -> float:
    """Sum of weights for all matching signals, capped at 1.0."""
    total = 0.0
    for pattern, weight in signals:
        if pattern.search(query):
            total += weight
    # Normalize: cap at 1.0 (many signals → high confidence)
    return min(total, 1.0)


def classify_query(query: str) -> QueryClassification:
    """Classify a user query into rag, metrics, or hybrid mode.

    Returns a QueryClassification with the mode and a confidence score.
    """
    metrics_score = _score(query, _METRICS_SIGNALS)
    rag_score = _score(query, _RAG_SIGNALS)

    # Both signal sets fire → hybrid
    if metrics_score > 0 and rag_score > 0:
        combined = (metrics_score + rag_score) / 2
        classification = QueryClassification(mode="hybrid", confidence=combined)
    elif metrics_score > 0:
        classification = QueryClassification(mode="metrics", confidence=metrics_score)
    else:
        # Default to rag (includes zero-signal queries)
        classification = QueryClassification(mode="rag", confidence=max(rag_score, 0.2))

    # Low-confidence fallback
    if classification.confidence < _CONFIDENCE_THRESHOLD:
        if metrics_score > 0:
            return QueryClassification(mode="hybrid", confidence=classification.confidence)
        return QueryClassification(mode="rag", confidence=classification.confidence)

    return classification
