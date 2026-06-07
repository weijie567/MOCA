from __future__ import annotations

# Single source for knowledge retrieval/rerank config version literals (RESEARCH GAP-3).
RETRIEVAL_CONFIG_VERSION = "retrieval.v3"
RERANK_CONFIG_VERSION = "rerank.v2"

# Thresholds mirror src/rag/retriever.py STRONG/MIN so facade status matches legacy behavior.
STRONG_EVIDENCE_THRESHOLD = 0.70
MIN_SIMILARITY_THRESHOLD = 0.55
