#!/usr/bin/env python3
"""Run Phase 6 retrieval benchmark sweeps across candidate/final K + reranker modes."""

from __future__ import annotations

import argparse
import itertools
import json
import os
import sys
from pathlib import Path
from typing import Any

# Import service modules directly from the repo.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "service"))

from app.config import Settings

from retrieval_eval_lib import (
    default_bq_project,
    default_golden_path,
    default_report_path,
    evaluate_retrieval,
    load_golden_queries,
    log_to_bigquery,
)


def _parse_csv_ints(raw: str) -> list[int]:
    values: list[int] = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        values.append(int(part))
    if not values:
        raise ValueError("at least one integer value is required")
    return values


def _parse_csv_strings(raw: str) -> list[str]:
    values = [value.strip() for value in raw.split(",") if value.strip()]
    if not values:
        raise ValueError("at least one value is required")
    return values


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Benchmark retrieval parameter sweeps")
    parser.add_argument(
        "--golden-file",
        type=Path,
        default=default_golden_path(),
        help="Path to retrieval golden set JSON",
    )
    parser.add_argument(
        "--candidate-k-values",
        type=str,
        default="10,20,30",
        help="Comma-separated candidate_k values",
    )
    parser.add_argument(
        "--final-k-values",
        type=str,
        default="3,5,7",
        help="Comma-separated final_k values",
    )
    parser.add_argument(
        "--reranker-modes",
        type=str,
        default="noop,cross_encoder",
        help="Comma-separated reranker modes (noop,cross_encoder)",
    )
    parser.add_argument(
        "--reranker-model",
        type=str,
        default=None,
        help="Cross-encoder model identifier (default: settings value)",
    )
    parser.add_argument(
        "--reranker-max-candidates",
        type=int,
        default=None,
        help="Max candidates scored by reranker (default: settings value)",
    )
    parser.add_argument(
        "--threshold-hit-at-k",
        type=float,
        default=0.70,
        help="Hit@K pass threshold",
    )
    parser.add_argument(
        "--threshold-mrr",
        type=float,
        default=0.55,
        help="MRR pass threshold",
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
        default="retrieval-sweep",
        help="Prefix used when writing per-configuration run labels to BigQuery",
    )
    parser.add_argument(
        "--no-threshold-gate",
        action="store_true",
        help="Always exit 0 even when best config misses thresholds",
    )
    return parser.parse_args()


def _run_row(
    *,
    settings: Settings,
    golden_queries: list[Any],
    candidate_k: int,
    final_k: int,
    reranker_mode: str,
    reranker_model: str,
    reranker_max_candidates: int,
    bq_project: str,
    bq_dataset: str,
    run_label_prefix: str,
) -> dict[str, Any]:
    report = evaluate_retrieval(
        settings=settings,
        golden_queries=golden_queries,
        candidate_k=candidate_k,
        final_k=final_k,
        reranker_mode=reranker_mode,
        reranker_model=reranker_model,
        reranker_max_candidates=reranker_max_candidates,
        fail_on_rerank_error=False,
    )
    summary = report["summary"]
    if bq_project and bq_dataset:
        run_label = (
            f"{run_label_prefix}:cand{candidate_k}:final{final_k}:"
            f"{summary['reranker_requested']}->{summary['reranker_effective']}"
        )
        log_to_bigquery(
            report=report,
            project_id=bq_project,
            dataset_id=bq_dataset,
            run_label=run_label,
        )

    return {
        "candidate_k": candidate_k,
        "final_k": final_k,
        "reranker_requested": reranker_mode,
        "reranker_effective": summary["reranker_effective"],
        "hit_at_k": summary["hit_at_k"],
        "mrr": summary["mrr"],
        "retrieval_latency_p95_ms": summary["retrieval_latency_p95_ms"],
        "total_latency_p95_ms": summary["total_latency_p95_ms"],
        "notes": summary["notes"],
    }


def _print_table(rows: list[dict[str, Any]], threshold_hit_at_k: float, threshold_mrr: float) -> None:
    print("Phase 6 Retrieval Sweep")
    print("=" * 120)
    header = (
        "candidate_k  final_k  reranker(req->effective)  "
        "hit@k    mrr     p95_retrieval_ms  p95_total_ms  pass"
    )
    print(header)
    print("-" * len(header))
    for row in rows:
        passed = row["hit_at_k"] >= threshold_hit_at_k and row["mrr"] >= threshold_mrr
        reranker_label = f"{row['reranker_requested']}->{row['reranker_effective']}"
        print(
            f"{row['candidate_k']:>11}  "
            f"{row['final_k']:>7}  "
            f"{reranker_label:<24}  "
            f"{row['hit_at_k']:<6.4f}  "
            f"{row['mrr']:<6.4f}  "
            f"{row['retrieval_latency_p95_ms']:>17.2f}  "
            f"{row['total_latency_p95_ms']:>12.2f}  "
            f"{'PASS' if passed else 'FAIL'}"
        )
        if row["notes"]:
            for note in row["notes"]:
                print(f"  note: {note}")


def main() -> None:
    args = parse_args()
    settings = Settings()
    golden_queries = load_golden_queries(args.golden_file)

    candidate_values = _parse_csv_ints(args.candidate_k_values)
    final_values = _parse_csv_ints(args.final_k_values)
    reranker_modes = _parse_csv_strings(args.reranker_modes)

    rows: list[dict[str, Any]] = []
    for candidate_k, final_k, reranker_mode in itertools.product(
        candidate_values, final_values, reranker_modes
    ):
        if final_k > candidate_k:
            continue
        rows.append(
            _run_row(
                settings=settings,
                golden_queries=golden_queries,
                candidate_k=candidate_k,
                final_k=final_k,
                reranker_mode=reranker_mode,
                reranker_model=args.reranker_model or settings.reranker_model,
                reranker_max_candidates=args.reranker_max_candidates or settings.reranker_max_candidates,
                bq_project=args.bq_project,
                bq_dataset=args.bq_dataset,
                run_label_prefix=args.run_label_prefix,
            )
        )

    if not rows:
        raise SystemExit("No valid benchmark combinations generated.")

    rows.sort(
        key=lambda row: (
            row["hit_at_k"],
            row["mrr"],
            -row["total_latency_p95_ms"],
        ),
        reverse=True,
    )

    _print_table(rows, args.threshold_hit_at_k, args.threshold_mrr)

    report = {
        "threshold_hit_at_k": args.threshold_hit_at_k,
        "threshold_mrr": args.threshold_mrr,
        "rows": rows,
    }
    report_file = args.report_file or default_report_path("retrieval-benchmark")
    report_file.parent.mkdir(parents=True, exist_ok=True)
    report_file.write_text(json.dumps(report, indent=2))
    print()
    print(f"Wrote benchmark report: {report_file}")

    best = rows[0]
    best_passed = best["hit_at_k"] >= args.threshold_hit_at_k and best["mrr"] >= args.threshold_mrr
    if not best_passed and not args.no_threshold_gate:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
