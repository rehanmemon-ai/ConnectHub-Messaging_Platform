"""Explicit synthetic-only live Gemini evaluation; never imported by normal app startup."""

import argparse
import asyncio
import json
import statistics
import time
from pathlib import Path

from app.ai.provider import GeminiProvider, embedding_profile
from app.ai.service import cosine_similarity
from app.core.config import Settings
from evals.dataset import DATASET_VERSION, MESSAGES, QUERIES
from evals.metrics import ndcg_at_k, precision_at_k, recall_at_k, reciprocal_rank_at_k
from evals.summary_dataset import DATASET_VERSION as SUMMARY_VERSION
from evals.summary_dataset import FIXTURES


async def retrieval(settings: Settings, output: Path, k: int, candidate_limit: int) -> None:
    provider = GeminiProvider(settings)
    document_vectors: dict[str, list[float]] = {}
    latencies: list[float] = []
    for message in MESSAGES:
        started = time.monotonic()
        document_vectors[message.id] = await provider.embed_document(message.text)
        latencies.append((time.monotonic() - started) * 1000)
    rows: list[dict[str, object]] = []
    candidates = MESSAGES[-candidate_limit:]
    for query in QUERIES:
        started = time.monotonic()
        query_vector = await provider.embed_query(query.text)
        latencies.append((time.monotonic() - started) * 1000)
        ranked = [
            item[1]
            for item in sorted(
                (
                    (cosine_similarity(query_vector, document_vectors[message.id]), message.id)
                    for message in candidates
                ),
                reverse=True,
            )
        ]
        relevant = {item for item, grade in query.relevance.items() if grade > 0}
        rows.append(
            {
                "query_id": query.id,
                "precision": precision_at_k(ranked, relevant, k),
                "recall": recall_at_k(ranked, relevant, k),
                "reciprocal_rank": reciprocal_rank_at_k(ranked, relevant, k),
                "ndcg": ndcg_at_k(ranked, query.relevance, k),
                "returned_ids": ranked[:k],
            }
        )
    metrics = {
        name: statistics.fmean(float(row[name]) for row in rows)
        for name in ("precision", "recall", "reciprocal_rank", "ndcg")
    }
    rendered = (
        json.dumps(
            {
                "dataset_version": DATASET_VERSION,
                "run_status": "LIVE_GEMINI_COMPLETED",
                "embedding_profile": embedding_profile(settings),
                "k": k,
                "candidate_limit": candidate_limit,
                "metrics": metrics,
                "provider_latency_ms": {
                    "mean": statistics.fmean(latencies),
                    "max": max(latencies),
                    "request_count": len(latencies),
                },
                "per_query": rows,
            },
            indent=2,
        )
        + "\n",
    )
    await asyncio.to_thread(output.write_text, rendered, encoding="utf-8")


async def summaries(settings: Settings, output: Path) -> None:
    provider = GeminiProvider(settings)
    rows: list[dict[str, object]] = []
    for fixture in FIXTURES:
        started = time.monotonic()
        summary = await provider.summarize(list(fixture.transcript))
        rows.append(
            {
                "fixture_id": fixture.id,
                "summary": summary,
                "required_facts": fixture.required_facts,
                "forbidden_claims_detected": [
                    claim
                    for claim in fixture.forbidden_claims
                    if claim.casefold() in summary.casefold()
                ],
                "duration_ms": round((time.monotonic() - started) * 1000, 2),
                "human_scores": None,
            }
        )
    rendered = (
        json.dumps(
            {
                "dataset_version": SUMMARY_VERSION,
                "run_status": "LIVE_GEMINI_COMPLETED_HUMAN_REVIEW_REQUIRED",
                "model": settings.ai_text_model,
                "fixtures": rows,
            },
            indent=2,
        )
        + "\n",
    )
    await asyncio.to_thread(output.write_text, rendered, encoding="utf-8")


async def async_main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--confirm-synthetic-only", action="store_true", required=True)
    parser.add_argument("--retrieval-output", type=Path)
    parser.add_argument("--summary-output", type=Path)
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--candidate-limit", type=int, default=120)
    args = parser.parse_args()
    if not args.retrieval_output and not args.summary_output:
        parser.error("select --retrieval-output and/or --summary-output")
    settings = Settings()
    if not settings.ai_enabled or settings.ai_api_key is None:
        parser.error("set AI_ENABLED=true and AI_API_KEY in the process environment")
    if args.retrieval_output:
        await retrieval(settings, args.retrieval_output, args.k, args.candidate_limit)
    if args.summary_output:
        await summaries(settings, args.summary_output)


if __name__ == "__main__":
    with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as runner:
        runner.run(async_main())
