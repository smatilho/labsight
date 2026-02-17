#!/usr/bin/env python3
"""Shared utilities for Phase 6 retrieval evaluation and benchmarking."""

from __future__ import annotations

import datetime as dt
import json
import math
import os
import statistics
import sys
import time
import uuid
from dataclasses import dataclass
from pathlib import Path, PurePath
from typing import Any

# Import service modules directly from the repo.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "service"))

from app.config import Settings
from app.rag.reranker import BaseReranker, CrossEncoderReranker, NoOpReranker
from app.rag.retriever import ChromaDBRetriever


@dataclass
class GoldenQuery:
    query: str
    expected_sources: list[str]


@dataclass
class QueryEvalResult:
    query_index: int
    query: str
    expected_sources: list[str]
    top_sources: list[str]
    hit: bool
    reciprocal_rank: float
    retrieval_latency_ms: float
    total_latency_ms: float
    candidate_count: int
    returned_count: int


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = math.ceil((percentile / 100.0) * len(ordered))
    idx = max(0, min(len(ordered) - 1, rank - 1))
    return round(ordered[idx], 2)


def _normalize_source(value: str) -> str:
    return value.strip().lower()


def _source_from_metadata(metadata: dict[str, Any]) -> str:
    source = metadata.get("source") or metadata.get("filename")
    if not isinstance(source, str) or not source:
        return "unknown"
    return PurePath(source).name


def _first_relevant_rank(top_sources: list[str], expected_sources: list[str]) -> int | None:
    if not expected_sources:
        return None

    normalized_expected = [_normalize_source(s) for s in expected_sources]
    for idx, source in enumerate(top_sources, start=1):
        normalized_source = _normalize_source(source)
        for expected in normalized_expected:
            if expected in normalized_source:
                return idx
    return None


def load_golden_queries(path: Path) -> list[GoldenQuery]:
    raw = json.loads(path.read_text())
    queries: list[GoldenQuery] = []
    for entry in raw:
        query = entry.get("query", "").strip()
        expected = entry.get("expected_sources", [])
        if not query:
            continue
        if not isinstance(expected, list):
            raise ValueError(f"Invalid expected_sources for query: {query}")
        queries.append(
            GoldenQuery(
                query=query,
                expected_sources=[str(value).strip() for value in expected if str(value).strip()],
            )
        )
    if not queries:
        raise ValueError(f"No golden queries found in {path}")
    return queries


def build_reranker(
    *,
    mode: str,
    model_name: str,
    max_candidates: int,
    fail_on_error: bool,
) -> tuple[BaseReranker, str, list[str]]:
    notes: list[str] = []
    normalized_mode = mode.strip().lower()

    if normalized_mode == "noop":
        return NoOpReranker(), "noop", notes

    if normalized_mode != "cross_encoder":
        raise ValueError("reranker mode must be one of: noop, cross_encoder")

    try:
        reranker = CrossEncoderReranker(
            model_name=model_name,
            max_candidates=max_candidates,
        )
        reranker.ensure_ready()
        return reranker, "cross_encoder", notes
    except Exception as exc:
        if fail_on_error:
            raise
        notes.append(
            "cross_encoder unavailable, falling back to noop "
            f"({type(exc).__name__}: {exc})"
        )
        return NoOpReranker(), "noop", notes


def evaluate_retrieval(
    *,
    settings: Settings,
    golden_queries: list[GoldenQuery],
    candidate_k: int,
    final_k: int,
    reranker_mode: str,
    reranker_model: str,
    reranker_max_candidates: int,
    fail_on_rerank_error: bool = False,
) -> dict[str, Any]:
    if candidate_k < final_k:
        raise ValueError("candidate_k must be >= final_k")
    if final_k <= 0:
        raise ValueError("final_k must be > 0")

    settings.retrieval_candidate_k = candidate_k
    retriever = ChromaDBRetriever(settings=settings)
    reranker, effective_mode, notes = build_reranker(
        mode=reranker_mode,
        model_name=reranker_model,
        max_candidates=reranker_max_candidates,
        fail_on_error=fail_on_rerank_error,
    )

    run_id = f"retrieval-eval-{dt.datetime.now(dt.timezone.utc).strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}"
    timestamp = dt.datetime.now(dt.timezone.utc).isoformat()

    results: list[QueryEvalResult] = []
    retrieval_latencies: list[float] = []
    total_latencies: list[float] = []

    for idx, case in enumerate(golden_queries, start=1):
        retrieval_started = time.perf_counter()
        candidate_docs = retriever.invoke(case.query)
        retrieval_ms = (time.perf_counter() - retrieval_started) * 1000

        total_started = time.perf_counter()
        selected_docs = reranker.rerank(
            query=case.query,
            docs=candidate_docs,
            top_k=final_k,
        )
        total_ms = (time.perf_counter() - total_started) * 1000 + retrieval_ms

        top_sources = [
            _source_from_metadata(doc.metadata or {})
            for doc in selected_docs
        ]
        rank = _first_relevant_rank(top_sources, case.expected_sources)
        hit = rank is not None
        reciprocal_rank = round(1.0 / rank, 4) if rank else 0.0

        results.append(
            QueryEvalResult(
                query_index=idx,
                query=case.query,
                expected_sources=case.expected_sources,
                top_sources=top_sources,
                hit=hit,
                reciprocal_rank=reciprocal_rank,
                retrieval_latency_ms=round(retrieval_ms, 2),
                total_latency_ms=round(total_ms, 2),
                candidate_count=len(candidate_docs),
                returned_count=len(selected_docs),
            )
        )
        retrieval_latencies.append(retrieval_ms)
        total_latencies.append(total_ms)

    hits = sum(1 for result in results if result.hit)
    query_count = len(results)
    hit_at_k = round(hits / query_count, 4) if query_count else 0.0
    mrr = (
        round(
            statistics.mean(result.reciprocal_rank for result in results),
            4,
        )
        if results
        else 0.0
    )

    summary = {
        "timestamp": timestamp,
        "run_id": run_id,
        "candidate_k": candidate_k,
        "final_k": final_k,
        "reranker_requested": reranker_mode,
        "reranker_effective": effective_mode,
        "reranker_model": reranker_model if effective_mode == "cross_encoder" else "",
        "reranker_max_candidates": reranker_max_candidates,
        "query_count": query_count,
        "hits": hits,
        "hit_at_k": hit_at_k,
        "mrr": mrr,
        "retrieval_latency_p50_ms": _percentile(retrieval_latencies, 50),
        "retrieval_latency_p95_ms": _percentile(retrieval_latencies, 95),
        "total_latency_p50_ms": _percentile(total_latencies, 50),
        "total_latency_p95_ms": _percentile(total_latencies, 95),
        "notes": notes,
    }

    return {
        "summary": summary,
        "results": [result.__dict__ for result in results],
    }


def print_report(report: dict[str, Any], *, threshold_hit_at_k: float, threshold_mrr: float) -> bool:
    summary = report["summary"]
    results = report["results"]

    print("Retrieval Evaluation Report")
    print("=" * 80)
    print(f"Run ID:              {summary['run_id']}")
    print(f"Timestamp:           {summary['timestamp']}")
    print(f"Candidate K:         {summary['candidate_k']}")
    print(f"Final K:             {summary['final_k']}")
    print(f"Reranker requested:  {summary['reranker_requested']}")
    print(f"Reranker effective:  {summary['reranker_effective']}")
    if summary["reranker_model"]:
        print(f"Reranker model:      {summary['reranker_model']}")
    print()
    print(f"Queries:             {summary['query_count']}")
    print(f"Hit@K:               {summary['hit_at_k']:.4f}")
    print(f"MRR:                 {summary['mrr']:.4f}")
    print(f"Retrieval latency:   p50={summary['retrieval_latency_p50_ms']:.2f}ms p95={summary['retrieval_latency_p95_ms']:.2f}ms")
    print(f"Total latency:       p50={summary['total_latency_p50_ms']:.2f}ms p95={summary['total_latency_p95_ms']:.2f}ms")
    if summary["notes"]:
        print("Notes:")
        for note in summary["notes"]:
            print(f"  - {note}")
    print()

    passed = summary["hit_at_k"] >= threshold_hit_at_k and summary["mrr"] >= threshold_mrr
    print(
        "Thresholds:          "
        f"Hit@K >= {threshold_hit_at_k:.2f}, MRR >= {threshold_mrr:.2f}"
    )
    print(f"Result:              {'PASS' if passed else 'FAIL'}")
    print()

    if not passed:
        print("Failed queries:")
        for row in results:
            if row["hit"]:
                continue
            print(f"  - [{row['query_index']}] {row['query']}")
            print(f"    expected: {row['expected_sources']}")
            print(f"    got:      {row['top_sources']}")
    return passed


def write_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2))


def log_to_bigquery(
    *,
    report: dict[str, Any],
    project_id: str,
    dataset_id: str,
    run_label: str,
) -> None:
    from google.cloud import bigquery

    summary = report["summary"]
    results = report["results"]
    now = dt.datetime.now(dt.timezone.utc).isoformat()

    run_table = f"{project_id}.{dataset_id}.retrieval_eval_runs"
    query_table = f"{project_id}.{dataset_id}.retrieval_eval_query_results"

    bq_client = bigquery.Client(project=project_id)

    run_row = {
        "timestamp": now,
        "run_id": summary["run_id"],
        "run_label": run_label,
        "reranker_requested": summary["reranker_requested"],
        "reranker_effective": summary["reranker_effective"],
        "reranker_model": summary["reranker_model"],
        "retrieval_candidate_k": int(summary["candidate_k"]),
        "retrieval_final_k": int(summary["final_k"]),
        "query_count": int(summary["query_count"]),
        "hit_at_k": float(summary["hit_at_k"]),
        "mrr": float(summary["mrr"]),
        "retrieval_latency_p50_ms": float(summary["retrieval_latency_p50_ms"]),
        "retrieval_latency_p95_ms": float(summary["retrieval_latency_p95_ms"]),
        "total_latency_p50_ms": float(summary["total_latency_p50_ms"]),
        "total_latency_p95_ms": float(summary["total_latency_p95_ms"]),
        "notes": " | ".join(summary["notes"]) if summary["notes"] else None,
    }

    run_errors = bq_client.insert_rows_json(run_table, [run_row])
    if run_errors:
        raise RuntimeError(f"BigQuery run insert errors: {run_errors}")

    query_rows: list[dict[str, Any]] = []
    for row in results:
        query_rows.append(
            {
                "timestamp": now,
                "run_id": summary["run_id"],
                "query_index": int(row["query_index"]),
                "query": row["query"],
                "expected_sources": row["expected_sources"],
                "top_sources": row["top_sources"],
                "hit": bool(row["hit"]),
                "reciprocal_rank": float(row["reciprocal_rank"]),
                "retrieval_latency_ms": float(row["retrieval_latency_ms"]),
                "total_latency_ms": float(row["total_latency_ms"]),
                "candidate_count": int(row["candidate_count"]),
                "returned_count": int(row["returned_count"]),
                "reranker_effective": summary["reranker_effective"],
            }
        )

    query_errors = bq_client.insert_rows_json(query_table, query_rows)
    if query_errors:
        raise RuntimeError(f"BigQuery query insert errors: {query_errors}")


def default_report_path(prefix: str) -> Path:
    ts = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d-%H%M%S")
    return ROOT / ".benchmarks" / "reports" / f"{prefix}-{ts}.json"


def default_golden_path() -> Path:
    return ROOT / ".benchmarks" / "retrieval_golden.json"


def default_bq_project() -> str:
    return os.getenv("LABSIGHT_GCP_PROJECT", "")
