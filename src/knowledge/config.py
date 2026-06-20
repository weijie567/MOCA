from __future__ import annotations

# Single source for knowledge retrieval/rerank config version literals (RESEARCH GAP-3).
RETRIEVAL_CONFIG_VERSION = "retrieval.v3"
RERANK_CONFIG_VERSION = "rerank.v2"
QUERY_REWRITE_CONFIG_VERSION = "query_rewrite.v1"

# Thresholds used by the knowledge-owned retrieval engine.
STRONG_EVIDENCE_THRESHOLD = 0.70
MIN_SIMILARITY_THRESHOLD = 0.55

# Phase 23 query rewrite bounds. Rewrite is local, deterministic, and additive.
QUERY_REWRITE_ENABLED = True
MAX_REWRITE_QUERIES = 3
MAX_REWRITE_QUERY_CHARS = 160
REWRITE_STAGE_TIMEOUT_SECONDS = 0.25
ORIGINAL_QUERY_TOP_K = 25
REWRITE_QUERY_TOP_K = 10
MERGED_CANDIDATE_CAP = 50

# Prompt-only policy text bounds. Full chunk content remains the source for text_hash.
MAX_EVIDENCE_TEXT_CHARS = 1600
MAX_PROMPT_EVIDENCE_ITEMS = 5
MAX_PROMPT_EVIDENCE_TOTAL_CHARS = MAX_EVIDENCE_TEXT_CHARS * MAX_PROMPT_EVIDENCE_ITEMS
