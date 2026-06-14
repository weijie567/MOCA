from __future__ import annotations

# Single source for knowledge retrieval/rerank config version literals (RESEARCH GAP-3).
RETRIEVAL_CONFIG_VERSION = "retrieval.v3"
RERANK_CONFIG_VERSION = "rerank.v2"

# Thresholds used by the knowledge-owned retrieval engine.
STRONG_EVIDENCE_THRESHOLD = 0.70
MIN_SIMILARITY_THRESHOLD = 0.55

# Prompt-only policy text bounds. Full chunk content remains the source for text_hash.
MAX_EVIDENCE_TEXT_CHARS = 1600
MAX_PROMPT_EVIDENCE_ITEMS = 5
MAX_PROMPT_EVIDENCE_TOTAL_CHARS = MAX_EVIDENCE_TEXT_CHARS * MAX_PROMPT_EVIDENCE_ITEMS
