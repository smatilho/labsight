#!/usr/bin/env python3
"""Golden query set for measuring router classification accuracy.

Runs ~20 queries through the heuristic router and compares against
expected classifications. Prints an accuracy report with misclassifications
and low-confidence queries highlighted.

Usage:
    python scripts/test_router_accuracy.py
"""

import sys
import os

# Add service/ to path so we can import the router directly
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "service"))

from app.agent.router import classify_query

# (query, expected_mode)
GOLDEN_QUERIES: list[tuple[str, str]] = [
    # Clear RAG — only RAG signals fire
    ("How did I configure DNS rewrite rules?", "rag"),
    ("How do I set up WireGuard?", "rag"),
    ("Where is the Dockerfile for the ingestion service?", "rag"),
    ("What port does Grafana use?", "rag"),
    ("What is the YAML configuration for Prometheus?", "rag"),
    # Clear metrics — only metrics signals fire
    ("Which service had the most downtime last week?", "metrics"),
    ("Show me CPU usage for pve01 yesterday", "metrics"),
    ("How many outages were there in the past month?", "metrics"),
    ("List all services that went down recently", "metrics"),
    # Hybrid — both RAG and metrics signals fire
    ("How is AdGuard configured and what's its current uptime?", "hybrid"),
    ("Is Proxmox using too much memory based on the docs?", "hybrid"),
    ("What is the setup for Plex and how much CPU does it use?", "hybrid"),
    # "What is the..." triggers RAG signal + metrics keywords → hybrid
    ("What is the average response time across all services?", "hybrid"),
    ("What is the current uptime for AdGuard?", "hybrid"),
    # docker-compose (RAG) + Uptime (metrics) → hybrid
    ("What's in my docker-compose for Uptime Kuma?", "hybrid"),
    # "going down" (metrics) without RAG signal → metrics
    ("Why does Nginx keep going down?", "metrics"),
    # Ambiguous / edge cases
    ("Tell me about my homelab", "rag"),
    ("Hello", "rag"),
    # "show me" is a weak metrics signal → metrics
    ("Show me everything", "metrics"),
    # "last Tuesday" — temporal but no strong metrics signal → rag fallback
    ("What happened last Tuesday?", "rag"),
]


def main() -> None:
    correct = 0
    total = len(GOLDEN_QUERIES)
    misclassified: list[tuple[str, str, str, float]] = []
    low_confidence: list[tuple[str, str, float]] = []

    for query, expected in GOLDEN_QUERIES:
        result = classify_query(query)

        if result.mode == expected:
            correct += 1
        else:
            misclassified.append((query, expected, result.mode, result.confidence))

        if result.confidence < 0.4:
            low_confidence.append((query, result.mode, result.confidence))

    accuracy = (correct / total) * 100

    print("Router Accuracy Report")
    print("=" * 50)
    print(f"Total queries:  {total}")
    print(f"Correct:        {correct} ({accuracy:.1f}%)")
    print(f"Misclassified:  {total - correct} ({100 - accuracy:.1f}%)")
    print()

    if misclassified:
        print("Misclassifications:")
        for query, expected, got, confidence in misclassified:
            print(f'  "{query}"')
            print(f"    expected: {expected}, got: {got} (confidence: {confidence:.2f})")
        print()

    if low_confidence:
        print(f"Low-confidence queries (< 0.4):")
        for query, mode, confidence in low_confidence:
            print(f'  "{query}" -> {mode} (confidence: {confidence:.2f})')
        print()

    # Exit with non-zero if accuracy is below 80%
    if accuracy < 80:
        print(f"FAIL: Accuracy {accuracy:.1f}% is below 80% threshold")
        sys.exit(1)
    else:
        print(f"PASS: Accuracy {accuracy:.1f}% meets 80% threshold")


if __name__ == "__main__":
    main()
