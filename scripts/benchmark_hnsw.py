#!/usr/bin/env python3
"""Benchmark HNSW parameter profiles against the retrieval golden set.

This script clones the current Chroma collection into local in-memory
collections with different HNSW settings, then measures retrieval quality
(Hit@K, MRR) and latency for each profile.
"""

from __future__ import annotations

import argparse
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
from app.rag.retriever import ChromaDBRetriever

from retrieval_eval_lib import (
    default_bq_project,
    default_golden_path,
    default_report_path,
    load_golden_queries,
)


@dataclass
class HNSWProfile:
    name: str
    m: int
    ef_construction: int
    ef_search: int


def _parse_profiles(raw: str) -> list[HNSWProfile]:
    profiles: list[HNSWProfile] = []
    if not raw.strip():
        return profiles

    for idx, part in enumerate(raw.split(";"), start=1):
        part = part.strip()
        if not part:
            continue
        # Format: name,m,ef_construction,ef_search
        fields = [field.strip() for field in part.split(",")]
        if len(fields) != 4:
            raise ValueError(
                "Invalid profile format. Expected: name,m,ef_construction,ef_search;..."
            )
        profiles.append(
            HNSWProfile(
                name=fields[0] or f"profile_{idx}",
                m=int(fields[1]),
                ef_construction=int(fields[2]),
                ef_search=int(fields[3]),
            )
        )
    return profiles


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = math.ceil((percentile / 100.0) * len(ordered))
    idx = max(0, min(len(ordered) - 1, rank - 1))
    return round(ordered[idx], 2)


def _source_from_metadata(metadata: dict[str, Any]) -> str:
    source = metadata.get("source") or metadata.get("filename")
    if not isinstance(source, str) or not source:
        return "unknown"
    return PurePath(source).name.lower()


def _first_rank(top_sources: list[str], expected_sources: list[str]) -> int | None:
    normalized_expected = [value.strip().lower() for value in expected_sources]
    for idx, source in enumerate(top_sources, start=1):
        for expected in normalized_expected:
            if expected and expected in source:
                return idx
    return None


def _clone_collection(
    *,
    profile: HNSWProfile,
    ids: list[str],
    embeddings: list[list[float]],
    documents: list[str],
    metadatas: list[dict[str, Any]],
) -> Any:
    import chromadb

    client = chromadb.Client()
    collection = client.create_collection(
        name=f"hnsw_{profile.name}_{int(time.time() * 1000)}",
        metadata={
            "hnsw:space": "l2",
            "hnsw:M": profile.m,
            "hnsw:construction_ef": profile.ef_construction,
            "hnsw:search_ef": profile.ef_search,
        },
    )

    batch_size = 200
    for start in range(0, len(ids), batch_size):
        end = start + batch_size
        collection.add(
            ids=ids[start:end],
            embeddings=embeddings[start:end],
            documents=documents[start:end],
            metadatas=metadatas[start:end],
        )
    return collection


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Benchmark HNSW profiles for retrieval quality")
    parser.add_argument(
        "--golden-file",
        type=Path,
        default=default_golden_path(),
        help="Path to retrieval golden set JSON",
    )
    parser.add_argument(
        "--candidate-k",
        type=int,
        default=10,
        help="Top K docs returned per query during benchmark",
    )
    parser.add_argument(
        "--profiles",
        type=str,
        default="baseline,16,100,50;high_recall,32,200,100;fast,8,64,20",
        help="Semicolon-separated profiles: name,m,ef_construction,ef_search",
    )
    parser.add_argument(
        "--report-file",
        type=Path,
        default=None,
        help="Where to write JSON report (default: .benchmarks/reports/...)",
    )
    parser.add_argument(
        "--bq-project",
        type=str,
        default=default_bq_project(),
        help="BigQuery project for optional logging (defaults to LABSIGHT_GCP_PROJECT)",
    )
    parser.add_argument(
        "--bq-dataset",
        type=str,
        default=os.getenv("LABSIGHT_RETRIEVAL_EVAL_BQ_DATASET", ""),
        help="BigQuery dataset for optional logging (e.g. platform_observability_dev)",
    )
    parser.add_argument(
        "--run-label-prefix",
        type=str,
        default="hnsw-benchmark",
        help="Prefix for BigQuery run labels",
    )
    return parser.parse_args()


def _log_profile_to_bigquery(
    *,
    project_id: str,
    dataset_id: str,
    run_label: str,
    profile_row: dict[str, Any],
    per_query_rows: list[dict[str, Any]],
) -> None:
    from google.cloud import bigquery

    bq_client = bigquery.Client(project=project_id)
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    run_id = f"hnsw-{profile_row['profile']}-{uuid.uuid4().hex[:8]}"

    run_table = f"{project_id}.{dataset_id}.retrieval_eval_runs"
    query_table = f"{project_id}.{dataset_id}.retrieval_eval_query_results"

    run_row = {
        "timestamp": now,
        "run_id": run_id,
        "run_label": run_label,
        "reranker_requested": f"hnsw:{profile_row['profile']}",
        "reranker_effective": "hnsw",
        "reranker_model": (
            f"M={profile_row['m']},ef_construction={profile_row['ef_construction']},"
            f"ef_search={profile_row['ef_search']}"
        ),
        "retrieval_candidate_k": int(profile_row["candidate_k"]),
        "retrieval_final_k": int(profile_row["candidate_k"]),
        "query_count": int(profile_row["query_count"]),
        "hit_at_k": float(profile_row["hit_at_k"]),
        "mrr": float(profile_row["mrr"]),
        "retrieval_latency_p50_ms": float(profile_row["latency_p50_ms"]),
        "retrieval_latency_p95_ms": float(profile_row["latency_p95_ms"]),
        "total_latency_p50_ms": float(profile_row["latency_p50_ms"]),
        "total_latency_p95_ms": float(profile_row["latency_p95_ms"]),
        "notes": "HNSW profile benchmark",
    }
    run_errors = bq_client.insert_rows_json(run_table, [run_row])
    if run_errors:
        raise RuntimeError(f"BigQuery run insert errors: {run_errors}")

    query_rows: list[dict[str, Any]] = []
    for row in per_query_rows:
        query_rows.append(
            {
                "timestamp": now,
                "run_id": run_id,
                "query_index": int(row["query_index"]),
                "query": row["query"],
                "expected_sources": row["expected_sources"],
                "top_sources": row["top_sources"],
                "hit": bool(row["hit"]),
                "reciprocal_rank": float(row["reciprocal_rank"]),
                "retrieval_latency_ms": float(row["latency_ms"]),
                "total_latency_ms": float(row["latency_ms"]),
                "candidate_count": int(profile_row["candidate_k"]),
                "returned_count": int(len(row["top_sources"])),
                "reranker_effective": "hnsw",
            }
        )

    query_errors = bq_client.insert_rows_json(query_table, query_rows)
    if query_errors:
        raise RuntimeError(f"BigQuery query insert errors: {query_errors}")


def main() -> None:
    args = parse_args()
    settings = Settings()
    golden_queries = load_golden_queries(args.golden_file)
    profiles = _parse_profiles(args.profiles)
    if not profiles:
        raise SystemExit("No HNSW profiles provided.")

    retriever = ChromaDBRetriever(settings=settings)
    remote_client = retriever._get_client()
    remote_collection = remote_client.get_collection(name=settings.chromadb_collection)
    corpus = remote_collection.get(include=["embeddings", "documents", "metadatas"])

    ids = corpus["ids"]
    embeddings = corpus["embeddings"]
    documents = corpus["documents"]
    metadatas = corpus["metadatas"]

    if not ids:
        raise SystemExit("Collection is empty; ingest documents before running HNSW benchmark.")

    rows: list[dict[str, Any]] = []
    for profile in profiles:
        local_collection = _clone_collection(
            profile=profile,
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
        )

        hits = 0
        reciprocal_ranks: list[float] = []
        latencies_ms: list[float] = []
        per_query_rows: list[dict[str, Any]] = []
        for case in golden_queries:
            query_embedding = retriever._embed_query(case.query)
            started = time.perf_counter()
            results = local_collection.query(
                query_embeddings=[query_embedding],
                n_results=args.candidate_k,
                include=["metadatas"],
            )
            latency_ms = (time.perf_counter() - started) * 1000
            latencies_ms.append(latency_ms)

            top_sources = [
                _source_from_metadata(metadata)
                for metadata in results["metadatas"][0]
            ]
            rank = _first_rank(top_sources, case.expected_sources)
            if rank is not None:
                hits += 1
                reciprocal_ranks.append(1.0 / rank)
            else:
                reciprocal_ranks.append(0.0)
            per_query_rows.append(
                {
                    "query_index": len(per_query_rows) + 1,
                    "query": case.query,
                    "expected_sources": case.expected_sources,
                    "top_sources": top_sources,
                    "hit": rank is not None,
                    "reciprocal_rank": round(1.0 / rank, 4) if rank else 0.0,
                    "latency_ms": round(latency_ms, 2),
                }
            )

        query_count = len(golden_queries)
        hit_at_k = round(hits / query_count, 4)
        mrr = round(statistics.mean(reciprocal_ranks), 4)
        row = {
            "profile": profile.name,
            "m": profile.m,
            "ef_construction": profile.ef_construction,
            "ef_search": profile.ef_search,
            "candidate_k": args.candidate_k,
            "query_count": query_count,
            "hit_at_k": hit_at_k,
            "mrr": mrr,
            "latency_p50_ms": _percentile(latencies_ms, 50),
            "latency_p95_ms": _percentile(latencies_ms, 95),
        }
        rows.append(row)

        if args.bq_project and args.bq_dataset:
            _log_profile_to_bigquery(
                project_id=args.bq_project,
                dataset_id=args.bq_dataset,
                run_label=f"{args.run_label_prefix}:{profile.name}",
                profile_row=row,
                per_query_rows=per_query_rows,
            )

    rows.sort(key=lambda row: (row["hit_at_k"], row["mrr"], -row["latency_p95_ms"]), reverse=True)

    print("HNSW Benchmark Report")
    print("=" * 110)
    print("profile        M   ef_construction  ef_search  hit@k   mrr    p50_ms  p95_ms")
    print("-" * 110)
    for row in rows:
        print(
            f"{row['profile']:<13} {row['m']:>2} "
            f"{row['ef_construction']:>17} {row['ef_search']:>10} "
            f"{row['hit_at_k']:<6.4f} {row['mrr']:<6.4f} "
            f"{row['latency_p50_ms']:>7.2f} {row['latency_p95_ms']:>7.2f}"
        )

    report = {
        "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(),
        "candidate_k": args.candidate_k,
        "profiles": rows,
    }
    report_file = args.report_file or default_report_path("hnsw-benchmark")
    report_file.parent.mkdir(parents=True, exist_ok=True)
    report_file.write_text(json.dumps(report, indent=2))
    print()
    print(f"Wrote HNSW benchmark report: {report_file}")


if __name__ == "__main__":
    main()
