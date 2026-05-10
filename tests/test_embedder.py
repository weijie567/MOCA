from __future__ import annotations

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
