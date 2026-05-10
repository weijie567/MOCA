from __future__ import annotations

import asyncio
import os

from openai import AsyncOpenAI

from src.config import settings


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
        self.batch_size = min(effective_batch_size, 10)
        self.max_retries = max_retries
        self._client: AsyncOpenAI | None = None

    def _get_client(self) -> AsyncOpenAI:
        if self._client is None:
            api_key = self._api_key or os.environ.get("DASHSCOPE_API_KEY")
            if not api_key:
                raise RuntimeError(
                    "DASHSCOPE_API_KEY not set. Provide api_key parameter or set the environment variable."
                )
            self._client = AsyncOpenAI(api_key=api_key, base_url=self._base_url)
        return self._client

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed multiple texts in batches. Raises on any failure."""
        results: list[list[float]] = []
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i : i + self.batch_size]
            embeddings = await self._embed_with_retry(batch)
            results.extend(embeddings)
        return results

    async def embed_query(self, text: str) -> list[float]:
        """Embed a single query text."""
        result = await self._embed_with_retry([text])
        return result[0]

    async def _embed_with_retry(self, texts: list[str]) -> list[list[float]]:
        client = self._get_client()
        for attempt in range(self.max_retries):
            try:
                response = await client.embeddings.create(
                    model=self.model,
                    input=texts,
                    dimensions=self.dimensions,
                )
                return [item.embedding for item in response.data]
            except Exception:
                if attempt == self.max_retries - 1:
                    raise
                await asyncio.sleep(2 ** attempt)
        raise RuntimeError("unreachable")
