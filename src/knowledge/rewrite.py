from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from src.knowledge.config import (
    MAX_REWRITE_QUERIES,
    MAX_REWRITE_QUERY_CHARS,
    QUERY_REWRITE_CONFIG_VERSION,
    QUERY_REWRITE_ENABLED,
)
from src.knowledge.schemas import KnowledgeContext


RewriteSource = Literal["domain_synonym", "intent_normalization", "merchant_support_alias"]
SkipReason = Literal[
    "already_specific",
    "out_of_domain",
    "unsafe_query",
    "missing_trusted_context",
    "disabled",
    "budget_exceeded",
    "error",
]


class RewriteExpansion(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    query: str
    source: RewriteSource
    matched_terms: tuple[str, ...] = ()


class QueryRewritePlan(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    original_query: str
    rewritten_queries: tuple[str, ...] = ()
    expansions: tuple[RewriteExpansion, ...] = ()
    skip_reason: SkipReason | None = None
    safe_summary: str | None = None
    trigger_terms: tuple[str, ...] = ()
    source: Literal["rule_default"] = "rule_default"
    config_version: str = QUERY_REWRITE_CONFIG_VERSION

    @property
    def should_rewrite(self) -> bool:
        return self.skip_reason is None and bool(self.expansions)


_TRUSTED_CONTEXT_FIELD_DENYLIST = {
    "tenant_id",
    "merchant_scope",
    "role",
    "risk_level",
    "doc_type",
    "effective_at",
    "effective_date",
    "policy_scope",
    "knowledge_scope",
}
_OUT_OF_DOMAIN_TRIGGERS = ("银行卡", "绑定手机号", "登录密码", "天气", "股票")
_UNSAFE_TRIGGERS = ("ignore previous instructions", "忽略之前", "泄露", "系统提示", "私钥")
_SPECIFIC_TRIGGERS = ("ORD-", "RF-", "退款时效", "跨境订单")
_DOMAIN_ANCHORS = ("补偿", "审批", "订单", "客服", "商家", "售后", "投诉", "物流", "退款", "退货", "运费", "跨境")
_NEEDS_REWRITE_CONTEXT_TERMS = ("已发货", "发了货", "补偿券", "七天无理由", "退款时效")
_ALREADY_SPECIFIC_ALIAS_TERMS = ("补偿券", "退款时效")
_ALIAS_RULES: tuple[tuple[str, str, RewriteSource], ...] = (
    ("仅退款", "仅退款 商家举证 物流状态", "domain_synonym"),
    ("已发货", "商家已发货 物流核实", "intent_normalization"),
    ("发了货", "商家已发货 物流核实", "intent_normalization"),
    ("补偿券", "补偿券 审批 材料", "merchant_support_alias"),
    ("七天无理由", "七天无理由 二次销售 退货退款", "domain_synonym"),
    ("退款时效", "退款时效 支付通道 超时", "intent_normalization"),
)


def build_query_rewrite_plan(
    query: str,
    context: KnowledgeContext | Mapping[str, Any] | None = None,
    *,
    trusted_context: KnowledgeContext | Mapping[str, Any] | None = None,
    enabled: bool = QUERY_REWRITE_ENABLED,
    max_expansions: int = MAX_REWRITE_QUERIES,
) -> QueryRewritePlan:
    original_query = query.strip()
    rewrite_context = context if context is not None else trusted_context

    if not enabled:
        return _skip(original_query, "disabled")
    if not _has_trusted_context(rewrite_context):
        return _skip(original_query, "missing_trusted_context")
    lowered = original_query.lower()
    if any(trigger in lowered or trigger in original_query for trigger in _UNSAFE_TRIGGERS):
        return _skip(original_query, "unsafe_query")
    if any(trigger in original_query for trigger in _OUT_OF_DOMAIN_TRIGGERS):
        return _skip(original_query, "out_of_domain")

    expansions = _build_expansions(original_query, max_expansions=max_expansions)
    if not expansions:
        if any(trigger in original_query for trigger in _SPECIFIC_TRIGGERS) or _has_domain_anchor(original_query):
            return _skip(original_query, "already_specific")
        return _skip(original_query, "out_of_domain")
    if any(term in original_query for term in _ALREADY_SPECIFIC_ALIAS_TERMS):
        return _skip(original_query, "already_specific")
    if _only_generic_refund_expansion(expansions) and not _has_rewrite_context(original_query):
        return _skip(original_query, "already_specific")

    trigger_terms = tuple(term for expansion in expansions for term in expansion.matched_terms)
    return QueryRewritePlan(
        original_query=original_query,
        rewritten_queries=tuple(expansion.query for expansion in expansions),
        expansions=tuple(expansions),
        safe_summary=_format_summary(rewrite_count=len(expansions), trigger_terms=trigger_terms),
        trigger_terms=trigger_terms,
    )


def safe_rewrite_summary(plan: QueryRewritePlan) -> str | None:
    return plan.safe_summary


def _build_expansions(query: str, *, max_expansions: int) -> list[RewriteExpansion]:
    limit = max(0, min(max_expansions, MAX_REWRITE_QUERIES))
    expansions: list[RewriteExpansion] = []
    seen_queries: set[str] = {query}

    for term, expansion_text, source in _ALIAS_RULES:
        if term not in query:
            continue
        rewritten = _bounded_query(f"{query} {expansion_text}")
        if rewritten in seen_queries:
            continue
        expansions.append(RewriteExpansion(query=rewritten, source=source, matched_terms=(term,)))
        seen_queries.add(rewritten)
        if len(expansions) >= limit:
            break
    return expansions


def _has_trusted_context(context: KnowledgeContext | Mapping[str, Any] | None) -> bool:
    if context is None:
        return False
    tenant_id = _context_value(context, "tenant_id")
    merchant_scope = _context_value(context, "merchant_scope")
    return bool(tenant_id) and bool(merchant_scope)


def _context_value(context: KnowledgeContext | Mapping[str, Any], key: str) -> Any:
    if isinstance(context, Mapping):
        return context.get(key)
    return getattr(context, key, None)


def _has_domain_anchor(query: str) -> bool:
    return any(anchor in query for anchor in _DOMAIN_ANCHORS)


def _only_generic_refund_expansion(expansions: list[RewriteExpansion]) -> bool:
    matched_terms = {term for expansion in expansions for term in expansion.matched_terms}
    return matched_terms == {"仅退款"}


def _has_rewrite_context(query: str) -> bool:
    return any(term in query for term in _NEEDS_REWRITE_CONTEXT_TERMS)


def _bounded_query(query: str) -> str:
    return query[:MAX_REWRITE_QUERY_CHARS].strip()


def _format_summary(*, rewrite_count: int, trigger_terms: tuple[str, ...]) -> str:
    triggers = ",".join(trigger_terms) if trigger_terms else "none"
    return f"rule_default: rewrite_count={rewrite_count}; triggers={triggers}"


def _skip(query: str, reason: SkipReason) -> QueryRewritePlan:
    return QueryRewritePlan(
        original_query=query,
        skip_reason=reason,
        safe_summary=f"rule_default: skip_reason={reason}; rewrite_count=0",
    )
