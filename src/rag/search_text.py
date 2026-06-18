from __future__ import annotations

import re
import unicodedata


DOMAIN_TERMS: tuple[str, ...] = (
    "仅退款",
    "七天无理由",
    "二次销售",
    "商家举证",
    "高价值订单",
    "补偿券",
    "退款时效",
    "跨境订单",
    "已发货",
    "发货",
    "商家",
    "退款",
    "退货",
    "售后",
    "物流",
    "举证",
    "申诉",
)

_ALNUM_PATTERN = re.compile(r"[a-z0-9]+")
_CJK_PATTERN = re.compile(r"[\u4e00-\u9fff]+")
_WHITESPACE_PATTERN = re.compile(r"\s+")
_TSQUERY_SAFE_PATTERN = re.compile(r"^[a-z0-9\u4e00-\u9fff]+$")
_QUESTION_PARTICLES = frozenset("吗呢嘛呀啊吧？?")


def normalize_search_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text).lower()
    return _WHITESPACE_PATTERN.sub(" ", normalized).strip()


def tokenize_search_text(text: str) -> list[str]:
    normalized = normalize_search_text(text)
    occurrences: list[tuple[int, int, int, str]] = []
    tokens: list[str] = []
    seen: set[str] = set()

    def add_occurrence(start: int, priority: int, length_priority: int, token: str) -> None:
        occurrences.append((start, priority, length_priority, token))

    def add_token(token: str) -> None:
        value = token.strip()
        if value and value not in seen:
            seen.add(value)
            tokens.append(value)

    for term in DOMAIN_TERMS:
        start = normalized.find(term)
        while start >= 0:
            add_occurrence(start, 0, -len(term), term)
            start = normalized.find(term, start + 1)

    for match in _ALNUM_PATTERN.finditer(normalized):
        add_occurrence(match.start(), 1, 0, match.group(0))

    for match in _CJK_PATTERN.finditer(normalized):
        segment = match.group(0)
        for size in (2, 3, 4):
            if len(segment) >= size:
                for index in range(len(segment) - size + 1):
                    add_occurrence(match.start() + index, 2, size, segment[index : index + size])

    for _, _, _, token in sorted(occurrences):
        add_token(token)

    return tokens


def build_policy_chunk_search_text(
    *,
    title: str,
    section: str,
    content: str,
    doc_type: str | None = None,
    risk_level: str | None = None,
) -> str:
    context_parts = [title, section, doc_type or "", risk_level or "", content]
    normalized_context = normalize_search_text(" ".join(part for part in context_parts if part))
    tokens = tokenize_search_text(normalized_context)
    parts = [normalized_context, *tokens]

    deduped: list[str] = []
    seen: set[str] = set()
    for part in parts:
        if part and part not in seen:
            seen.add(part)
            deduped.append(part)
    return " ".join(deduped)


def build_sparse_query_text(text: str, *, max_terms: int = 16) -> str:
    """Build a bounded PostgreSQL tsquery expression over application tokens.

    `plainto_tsquery` treats all terms as required, which is too strict for
    Chinese n-gram query text. We generate an OR expression from trusted tokens
    so sparse retrieval can match the important anchors without requiring every
    generated n-gram to appear in a chunk.
    """
    normalized = normalize_search_text(text)
    tokens = tokenize_search_text(normalized)

    terms: list[str] = []
    seen: set[str] = set()

    def add(term: str) -> None:
        if term not in seen and _is_sparse_query_term(term):
            seen.add(term)
            terms.append(term)

    for token in tokens:
        if token in DOMAIN_TERMS:
            add(token)
    for token in tokens:
        if token not in DOMAIN_TERMS:
            add(token)
        if len(terms) >= max_terms:
            break

    return " | ".join(terms[:max_terms])


def _is_sparse_query_term(term: str) -> bool:
    return len(term) >= 2 and _TSQUERY_SAFE_PATTERN.fullmatch(term) is not None and not (
        _QUESTION_PARTICLES & set(term)
    )
