from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.config import settings
from src.rag.embedder import EmbeddingService


def test_embedding_service_defaults_from_settings(monkeypatch):
    monkeypatch.setattr(settings, "embedding_base_url", "https://example.test/v1")
    monkeypatch.setattr(settings, "embedding_model", "custom-embedding")
    monkeypatch.setattr(settings, "embedding_dimensions", 512)
    monkeypatch.setattr(settings, "embedding_batch_size", 12)

    service = EmbeddingService(api_key="test-key")

    assert service._base_url == "https://example.test/v1"
    assert service.model == "custom-embedding"
    assert service.dimensions == 512
    assert service.batch_size == 10


def test_embedding_service_uses_settings_api_key_before_environment(monkeypatch):
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    for key in ("ALL_PROXY", "HTTPS_PROXY", "HTTP_PROXY", "all_proxy", "https_proxy", "http_proxy"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(settings, "dashscope_api_key", "settings-key")

    service = EmbeddingService()
    client = service._get_client()

    assert client.api_key == "settings-key"
    assert client.max_retries == 0


@pytest.mark.asyncio
async def test_embedding_service_owns_retries_outside_sdk(monkeypatch) -> None:
    calls = 0

    class _Embeddings:
        async def create(self, **_kwargs):
            nonlocal calls
            calls += 1
            if calls < 3:
                raise RuntimeError("safe test failure")
            return SimpleNamespace(
                data=[SimpleNamespace(index=0, embedding=[1.0, 2.0])],
                usage=SimpleNamespace(prompt_tokens=2, total_tokens=2),
            )

    async def no_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr("src.rag.embedder.asyncio.sleep", no_sleep)
    service = EmbeddingService(api_key="test-key", dimensions=2, max_retries=3)
    service._client = SimpleNamespace(embeddings=_Embeddings())  # type: ignore[assignment]

    assert await service.embed_documents(["document"]) == [[1.0, 2.0]]
    assert calls == 3


@pytest.mark.asyncio
async def test_vector_only_wrappers_preserve_existing_list_contract() -> None:
    calls: list[list[str]] = []

    class _Embeddings:
        async def create(self, **kwargs):
            calls.append(kwargs["input"])
            vectors = [[float(index), 1.0] for index, _ in enumerate(kwargs["input"])]
            return SimpleNamespace(
                data=[SimpleNamespace(index=index, embedding=vector) for index, vector in enumerate(vectors)],
                usage=SimpleNamespace(prompt_tokens=7, total_tokens=7),
            )

    service = EmbeddingService(api_key="test-key", dimensions=2)
    service._client = SimpleNamespace(embeddings=_Embeddings())  # type: ignore[assignment]

    documents = await service.embed_documents(["first", "second"])
    query = await service.embed_query("query")

    assert documents == [[0.0, 1.0], [1.0, 1.0]]
    assert query == [0.0, 1.0]
    assert calls == [["first", "second"], ["query"]]
