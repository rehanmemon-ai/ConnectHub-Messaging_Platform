import json

import httpx
import pytest

from app.ai.provider import AiProviderError, GeminiProvider
from app.core.config import Settings


def settings(**overrides):  # type: ignore[no-untyped-def]
    return Settings(
        ai_enabled=True,
        ai_api_key="x" * 40,
        ai_embedding_dimensions=128,
        **overrides,
    )


async def test_gemini_provider_parses_summary_and_embedding_without_sdk() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["x-goog-api-key"] == "x" * 40
        if request.url.path.endswith(":generateContent"):
            return httpx.Response(
                200,
                json={"candidates": [{"content": {"parts": [{"text": "Safe summary"}]}}]},
            )
        payload = json.loads(request.content)
        assert payload["taskType"] in {"RETRIEVAL_DOCUMENT", "RETRIEVAL_QUERY"}
        assert payload["outputDimensionality"] == 128
        return httpx.Response(200, json={"embedding": {"values": [0.5] * 128}})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = GeminiProvider(settings(), client)
        assert await provider.summarize(["untrusted text"]) == "Safe summary"
        assert len(await provider.embed_document("document")) == 128
        assert len(await provider.embed_query("query")) == 128


async def test_gemini_provider_missing_key_and_invalid_response_are_safe() -> None:
    disabled = GeminiProvider(Settings(ai_enabled=False))
    with pytest.raises(AiProviderError, match="not configured"):
        await disabled.embed_query("query")

    async def malformed(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"unexpected": True})

    async with httpx.AsyncClient(transport=httpx.MockTransport(malformed)) as client:
        provider = GeminiProvider(settings(), client)
        with pytest.raises(AiProviderError) as error:
            await provider.summarize(["text"])
        assert error.value.code == "ai_invalid_response"


@pytest.mark.parametrize("invalid", [float("nan"), float("inf"), True])
async def test_gemini_provider_rejects_nonfinite_and_boolean_embeddings(invalid) -> None:  # type: ignore[no-untyped-def]
    async def malformed(_: httpx.Request) -> httpx.Response:
        body = json.dumps({"embedding": {"values": [invalid] * 128}}, allow_nan=True)
        return httpx.Response(200, content=body, headers={"content-type": "application/json"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(malformed)) as client:
        provider = GeminiProvider(settings(), client)
        with pytest.raises(AiProviderError) as error:
            await provider.embed_document("synthetic")
        assert error.value.code == "ai_invalid_response"
