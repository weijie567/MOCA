from __future__ import annotations

from dataclasses import FrozenInstanceError, fields
from types import SimpleNamespace
from typing import Any

import pytest

from src.rag.embedder import (
    EmbeddingBatchResultV1,
    EmbeddingRequestUsageV1,
    EmbeddingService,
    EmbeddingUsageStatus,
)


class _FakeEmbeddings:
    def __init__(self, responses: list[object]) -> None:
        self.responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    async def create(self, **kwargs: Any) -> object:
        self.calls.append(kwargs)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class _FakeClient:
    def __init__(self, responses: list[object]) -> None:
        self.embeddings = _FakeEmbeddings(responses)


def _response(
    *,
    vectors: list[list[float]],
    prompt_tokens: int | None,
    total_tokens: int | None,
    reverse_data: bool = False,
) -> object:
    data = [SimpleNamespace(index=index, embedding=vector) for index, vector in enumerate(vectors)]
    if reverse_data:
        data.reverse()
    usage = (
        None
        if prompt_tokens is None and total_tokens is None
        else SimpleNamespace(prompt_tokens=prompt_tokens, total_tokens=total_tokens)
    )
    return SimpleNamespace(data=data, usage=usage)


def _service(
    responses: list[object], *, batch_size: int = 10, max_retries: int = 3
) -> tuple[EmbeddingService, _FakeClient]:
    service = EmbeddingService(
        api_key="synthetic-key",
        base_url="https://example.invalid/v1",
        model="text-embedding-v4",
        dimensions=2,
        batch_size=batch_size,
        max_retries=max_retries,
    )
    client = _FakeClient(responses)
    service._client = client  # type: ignore[assignment]
    return service, client


def test_usage_dtos_are_frozen_and_expose_only_safe_request_level_fields() -> None:
    assert {field.name for field in fields(EmbeddingRequestUsageV1)} == {
        "request_index",
        "input_count",
        "prompt_tokens",
        "total_tokens",
        "status",
    }
    assert {field.name for field in fields(EmbeddingBatchResultV1)} == {
        "embeddings",
        "request_usages",
        "prompt_tokens",
        "total_tokens",
        "usage_status",
    }

    usage = EmbeddingRequestUsageV1(
        request_index=0,
        input_count=2,
        prompt_tokens=11,
        total_tokens=11,
        status=EmbeddingUsageStatus.REPORTED,
    )
    with pytest.raises(FrozenInstanceError):
        usage.prompt_tokens = 6  # type: ignore[misc]


@pytest.mark.asyncio
async def test_embed_documents_with_usage_retains_request_totals_without_per_input_allocation() -> None:
    first_vectors = [[float(index), 0.0] for index in range(10)]
    second_vectors = [[10.0, 0.0], [11.0, 0.0]]
    service, client = _service(
        [
            _response(vectors=first_vectors, prompt_tokens=101, total_tokens=101, reverse_data=True),
            _response(vectors=second_vectors, prompt_tokens=23, total_tokens=23),
        ],
        batch_size=99,
    )

    result = await service.embed_documents_with_usage([f"synthetic-{index}" for index in range(12)])

    assert result.embeddings == tuple(tuple(vector) for vector in (*first_vectors, *second_vectors))
    assert result.request_usages == (
        EmbeddingRequestUsageV1(
            request_index=0,
            input_count=10,
            prompt_tokens=101,
            total_tokens=101,
            status=EmbeddingUsageStatus.REPORTED,
        ),
        EmbeddingRequestUsageV1(
            request_index=1,
            input_count=2,
            prompt_tokens=23,
            total_tokens=23,
            status=EmbeddingUsageStatus.REPORTED,
        ),
    )
    assert result.prompt_tokens == 124
    assert result.total_tokens == 124
    assert result.usage_status is EmbeddingUsageStatus.REPORTED
    assert [len(call["input"]) for call in client.embeddings.calls] == [10, 2]
    assert all(call["dimensions"] == 2 for call in client.embeddings.calls)
    assert all(call["model"] == "text-embedding-v4" for call in client.embeddings.calls)


@pytest.mark.asyncio
async def test_missing_request_usage_makes_only_aggregate_usage_unavailable() -> None:
    service, _ = _service(
        [
            _response(vectors=[[1.0, 0.0], [2.0, 0.0]], prompt_tokens=9, total_tokens=9),
            _response(vectors=[[3.0, 0.0]], prompt_tokens=None, total_tokens=None),
        ],
        batch_size=2,
    )

    result = await service.embed_documents_with_usage(["one", "two", "three"])

    assert result.request_usages[0].status is EmbeddingUsageStatus.REPORTED
    assert result.request_usages[0].prompt_tokens == 9
    assert result.request_usages[1] == EmbeddingRequestUsageV1(
        request_index=1,
        input_count=1,
        prompt_tokens=None,
        total_tokens=None,
        status=EmbeddingUsageStatus.UNAVAILABLE,
    )
    assert result.prompt_tokens is None
    assert result.total_tokens is None
    assert result.usage_status is EmbeddingUsageStatus.UNAVAILABLE


@pytest.mark.asyncio
async def test_usage_path_preserves_retry_behavior_without_retaining_provider_failure() -> None:
    service, client = _service(
        [
            RuntimeError("raw provider detail must not enter a result"),
            _response(vectors=[[1.0, 2.0]], prompt_tokens=5, total_tokens=5),
        ],
        max_retries=2,
    )

    result = await service.embed_documents_with_usage(["safe synthetic input"])

    assert result.embeddings == ((1.0, 2.0),)
    assert result.prompt_tokens == 5
    assert len(client.embeddings.calls) == 2
    assert "provider" not in repr(result).lower()
