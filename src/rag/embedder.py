from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from openai import AsyncOpenAI

from src.config import settings


class EmbeddingUsageStatus(StrEnum):
    REPORTED = "reported"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class EmbeddingRequestUsageV1:
    request_index: int
    input_count: int
    prompt_tokens: int | None
    total_tokens: int | None
    status: EmbeddingUsageStatus


@dataclass(frozen=True, slots=True)
class EmbeddingBatchResultV1:
    embeddings: tuple[tuple[float, ...], ...]
    request_usages: tuple[EmbeddingRequestUsageV1, ...]
    prompt_tokens: int | None
    total_tokens: int | None
    usage_status: EmbeddingUsageStatus


@dataclass(frozen=True, slots=True)
class _EmbeddingRequestResult:
    embeddings: tuple[tuple[float, ...], ...]
    usage: EmbeddingRequestUsageV1


class EmbeddingService:
    """DashScope text-embedding-v4 wrapper via OpenAI-compatible API."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        dimensions: int | None = None,
        batch_size: int | None = None,
        max_retries: int = 3,
    ):
        self._api_key = api_key
        self._base_url = base_url or settings.embedding_base_url
        self.model = model or settings.embedding_model
        self.dimensions = dimensions if dimensions is not None else settings.embedding_dimensions
        effective_batch_size = batch_size if batch_size is not None else settings.embedding_batch_size
        if type(effective_batch_size) is not int or effective_batch_size <= 0:
            raise ValueError("invalid_embedding_batch_size")
        if type(max_retries) is not int or max_retries <= 0:
            raise ValueError("invalid_embedding_max_retries")
        self.batch_size = min(effective_batch_size, 10)
        self.max_retries = max_retries
        self._client: AsyncOpenAI | None = None

    def _get_client(self) -> AsyncOpenAI:
        if self._client is None:
            api_key = self._api_key or settings.dashscope_api_key or os.environ.get("DASHSCOPE_API_KEY")
            if not api_key:
                raise RuntimeError(
                    "DASHSCOPE_API_KEY not set. Provide api_key parameter or set the environment variable."
                )
            self._client = AsyncOpenAI(api_key=api_key, base_url=self._base_url)
        return self._client

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed multiple texts in batches. Raises on any failure."""
        result = await self.embed_documents_with_usage(texts)
        return [list(vector) for vector in result.embeddings]

    async def embed_documents_with_usage(self, texts: list[str]) -> EmbeddingBatchResultV1:
        """Embed texts while retaining only truthful request-level provider usage."""
        embeddings: list[tuple[float, ...]] = []
        request_usages: list[EmbeddingRequestUsageV1] = []
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i : i + self.batch_size]
            request = await self._embed_request_with_retry(
                batch,
                request_index=len(request_usages),
            )
            embeddings.extend(request.embeddings)
            request_usages.append(request.usage)

        all_reported = bool(request_usages) and all(
            usage.status is EmbeddingUsageStatus.REPORTED for usage in request_usages
        )
        prompt_tokens = (
            sum(usage.prompt_tokens for usage in request_usages if usage.prompt_tokens is not None)
            if all_reported
            else None
        )
        total_tokens = (
            sum(usage.total_tokens for usage in request_usages if usage.total_tokens is not None)
            if all_reported
            else None
        )
        usage_status = EmbeddingUsageStatus.REPORTED if all_reported else EmbeddingUsageStatus.UNAVAILABLE
        return EmbeddingBatchResultV1(
            embeddings=tuple(embeddings),
            request_usages=tuple(request_usages),
            prompt_tokens=prompt_tokens,
            total_tokens=total_tokens,
            usage_status=usage_status,
        )

    async def embed_query(self, text: str) -> list[float]:
        """Embed a single query text."""
        result = await self._embed_with_retry([text])
        return result[0]

    async def _embed_with_retry(self, texts: list[str]) -> list[list[float]]:
        """Compatibility wrapper retaining the existing vector-only private seam."""
        result = await self._embed_request_with_retry(texts, request_index=0)
        return [list(vector) for vector in result.embeddings]

    async def _embed_request_with_retry(
        self,
        texts: list[str],
        *,
        request_index: int,
    ) -> _EmbeddingRequestResult:
        client = self._get_client()
        for attempt in range(self.max_retries):
            try:
                response = await client.embeddings.create(
                    model=self.model,
                    input=texts,
                    dimensions=self.dimensions,
                )
                embeddings = self._ordered_embeddings(response, expected_count=len(texts))
                usage = self._request_usage(
                    response,
                    request_index=request_index,
                    input_count=len(texts),
                )
                return _EmbeddingRequestResult(embeddings=embeddings, usage=usage)
            except Exception:
                if attempt == self.max_retries - 1:
                    raise
                await asyncio.sleep(2**attempt)
        raise RuntimeError("unreachable")

    def _ordered_embeddings(self, response: Any, *, expected_count: int) -> tuple[tuple[float, ...], ...]:
        try:
            data = tuple(response.data)
            indexed = sorted(((item.index, item.embedding) for item in data), key=lambda pair: pair[0])
        except Exception:
            raise RuntimeError("embedding_response_invalid") from None
        if [index for index, _ in indexed] != list(range(expected_count)):
            raise RuntimeError("embedding_response_invalid")

        vectors: list[tuple[float, ...]] = []
        for _, vector in indexed:
            try:
                frozen = tuple(float(value) for value in vector)
            except (TypeError, ValueError):
                raise RuntimeError("embedding_response_invalid") from None
            if len(frozen) != self.dimensions:
                raise RuntimeError("embedding_response_invalid")
            vectors.append(frozen)
        return tuple(vectors)

    @staticmethod
    def _request_usage(
        response: Any,
        *,
        request_index: int,
        input_count: int,
    ) -> EmbeddingRequestUsageV1:
        usage = getattr(response, "usage", None)
        prompt_tokens = _safe_usage_count(getattr(usage, "prompt_tokens", None))
        total_tokens = _safe_usage_count(getattr(usage, "total_tokens", None))
        if prompt_tokens is None or total_tokens is None:
            return EmbeddingRequestUsageV1(
                request_index=request_index,
                input_count=input_count,
                prompt_tokens=None,
                total_tokens=None,
                status=EmbeddingUsageStatus.UNAVAILABLE,
            )
        return EmbeddingRequestUsageV1(
            request_index=request_index,
            input_count=input_count,
            prompt_tokens=prompt_tokens,
            total_tokens=total_tokens,
            status=EmbeddingUsageStatus.REPORTED,
        )


def _safe_usage_count(value: object) -> int | None:
    if type(value) is not int or value < 0:
        return None
    return value
