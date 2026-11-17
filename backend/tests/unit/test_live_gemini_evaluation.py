import json
from pathlib import Path

import pytest
from pydantic import SecretStr

from app.core.config import Settings
from evals import run_live_gemini


class FakeGeminiProvider:
    def __init__(self, settings: Settings) -> None:
        self.dimensions = settings.ai_embedding_dimensions

    async def embed_document(self, text: str) -> list[float]:
        return [1.0] + [0.0] * (self.dimensions - 1)

    async def embed_query(self, text: str) -> list[float]:
        return [1.0] + [0.0] * (self.dimensions - 1)

    async def summarize(self, messages: list[str]) -> str:
        return f"Synthetic summary of {len(messages)} messages"


def evaluation_settings() -> Settings:
    return Settings(
        ai_enabled=True,
        ai_api_key=SecretStr("synthetic-test-key-not-a-real-secret"),
        ai_embedding_dimensions=128,
    )


async def test_live_retrieval_and_summary_outputs_are_valid_json(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(run_live_gemini, "GeminiProvider", FakeGeminiProvider)
    retrieval_path = tmp_path / "retrieval.json"
    summary_path = tmp_path / "summaries.json"

    await run_live_gemini.retrieval(evaluation_settings(), retrieval_path, 5, 120)
    await run_live_gemini.summaries(evaluation_settings(), summary_path)

    retrieval_text = retrieval_path.read_text(encoding="utf-8")
    summary_text = summary_path.read_text(encoding="utf-8")
    retrieval = json.loads(retrieval_text)
    summaries = json.loads(summary_text)
    assert retrieval["run_status"] == "LIVE_GEMINI_COMPLETED"
    assert set(retrieval["metrics"]) == {
        "precision",
        "recall",
        "reciprocal_rank",
        "ndcg",
        "average_precision",
    }
    assert summaries["run_status"] == "LIVE_GEMINI_COMPLETED_HUMAN_REVIEW_REQUIRED"
    assert len(summaries["fixtures"]) == 18
    assert "synthetic-test-key" not in retrieval_text + summary_text


async def test_live_evaluation_propagates_output_write_errors(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(run_live_gemini, "GeminiProvider", FakeGeminiProvider)
    with pytest.raises(FileNotFoundError):
        await run_live_gemini.summaries(
            evaluation_settings(), tmp_path / "missing-directory" / "summary.json"
        )
