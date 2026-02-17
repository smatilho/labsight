#!/usr/bin/env python3
"""Run Phase 6 retrieval evaluation against a golden query set.

Usage examples:
  python scripts/eval_retrieval.py
  python scripts/eval_retrieval.py --reranker cross_encoder --candidate-k 30 --final-k 5
  python scripts/eval_retrieval.py --bq-dataset platform_observability_dev --run-label baseline-noop
"""

import argparse
import os
import sys
from pathlib import Path

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
    print_report,
    write_report,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate Labsight retrieval quality")
    parser.add_argument(
        "--golden-file",
        type=Path,
        default=default_golden_path(),
        help="Path to retrieval golden set JSON",
    )
    parser.add_argument(
        "--candidate-k",
        type=int,
        default=None,
        help="Candidate documents retrieved from ChromaDB (default: settings value)",
    )
    parser.add_argument(
        "--final-k",
        type=int,
        default=None,
        help="Final documents passed to context after reranking (default: settings value)",
    )
    parser.add_argument(
        "--reranker",
        choices=["noop", "cross_encoder"],
        default="noop",
        help="Reranker mode for this run",
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
        "--fail-on-rerank-error",
        action="store_true",
        help="Fail instead of falling back when cross-encoder dependencies are unavailable",
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
        "--run-label",
        type=str,
        default="",
        help="Optional run label for BigQuery rows",
    )
    parser.add_argument(
        "--no-threshold-gate",
        action="store_true",
        help="Always exit 0 even when thresholds fail (useful while corpus is still small)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    settings = Settings()

    golden_queries = load_golden_queries(args.golden_file)
    report = evaluate_retrieval(
        settings=settings,
        golden_queries=golden_queries,
        candidate_k=args.candidate_k or settings.retrieval_candidate_k,
        final_k=args.final_k or settings.retrieval_final_k,
        reranker_mode=args.reranker,
        reranker_model=args.reranker_model or settings.reranker_model,
        reranker_max_candidates=args.reranker_max_candidates or settings.reranker_max_candidates,
        fail_on_rerank_error=args.fail_on_rerank_error,
    )

    report_file = args.report_file or default_report_path("retrieval-eval")
    write_report(report_file, report)
    print(f"Wrote report: {report_file}")
    print()

    passed = print_report(
        report,
        threshold_hit_at_k=args.threshold_hit_at_k,
        threshold_mrr=args.threshold_mrr,
    )

    if args.bq_project and args.bq_dataset:
        log_to_bigquery(
            report=report,
            project_id=args.bq_project,
            dataset_id=args.bq_dataset,
            run_label=args.run_label,
        )
        print(
            "Logged run to BigQuery tables: "
            f"{args.bq_project}.{args.bq_dataset}.retrieval_eval_runs and "
            f"{args.bq_project}.{args.bq_dataset}.retrieval_eval_query_results"
        )

    if not passed and not args.no_threshold_gate:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
