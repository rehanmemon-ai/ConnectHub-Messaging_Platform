"""Run the deterministic exact-substring baseline; live Gemini is separate and opt-in."""

import argparse
import json
import statistics
import time
from pathlib import Path

from evals.dataset import DATASET_VERSION, MESSAGES, QUERIES
from evals.metrics import (
    average_precision_at_k,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
    reciprocal_rank_at_k,
)


def exact_substring_rank(query: str, candidate_limit: int | None = None) -> list[str]:
    candidates = MESSAGES[-candidate_limit:] if candidate_limit else MESSAGES
    needle = query.casefold()
    return [message.id for message in reversed(candidates) if needle in message.text.casefold()]


def evaluate(k: int, candidate_limit: int | None) -> dict[str, object]:
    rows: list[dict[str, object]] = []
    latencies: list[float] = []
    for query in QUERIES:
        started = time.perf_counter()
        ranked = exact_substring_rank(query.text, candidate_limit)
        latencies.append((time.perf_counter() - started) * 1000)
        relevant = {item for item, grade in query.relevance.items() if grade > 0}
        rows.append(
            {
                "query_id": query.id,
                "category": query.category,
                "precision": precision_at_k(ranked, relevant, k),
                "recall": recall_at_k(ranked, relevant, k),
                "reciprocal_rank": reciprocal_rank_at_k(ranked, relevant, k),
                "ndcg": ndcg_at_k(ranked, query.relevance, k),
                "average_precision": average_precision_at_k(ranked, relevant, k),
                "returned_ids": ranked[:k],
            }
        )
    metric_names = ("precision", "recall", "reciprocal_rank", "ndcg", "average_precision")
    return {
        "dataset_version": DATASET_VERSION,
        "system": "literal_case_insensitive_substring_baseline",
        "semantic_model": None,
        "semantic_quality_status": "NOT_RUN",
        "message_count": len(MESSAGES),
        "query_count": len(QUERIES),
        "k": k,
        "candidate_limit": candidate_limit,
        "metrics": {
            name: statistics.fmean(float(row[name]) for row in rows) for name in metric_names
        },
        "latency_ms": {
            "mean": statistics.fmean(latencies),
            "max": max(latencies),
        },
        "per_query": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--candidate-limit", type=int)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = evaluate(args.k, args.candidate_limit)
    rendered = json.dumps(result, indent=2)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)


if __name__ == "__main__":
    main()
