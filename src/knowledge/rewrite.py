from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

from src.knowledge.config import (
    MAX_REWRITE_QUERIES,
    MAX_REWRITE_QUERY_CHARS,
    QUERY_REWRITE_CONFIG_VERSION,
)
from src.knowledge.schemas import KnowledgeContext


RewriteSource = Literal["domain_synonym", "intent_normalization", "merchant_support_alias"]
RewriteSkipReason = Literal[
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
    skip_reason: RewriteSkipReason | None = None
    safe_summary: str | None = None
    trigger_terms: tuple[str, ...] = ()
    source: Literal["rule_default"] = "rule_default"
    config_version: str = QUERY_REWRITE_CONFIG_VERSION


# No-widening denylist for trusted filters/scopes: these names must never become rewrite DTO fields.
TRUSTED_FILTER_FIELD_DENYLIST: tuple[str, ...] = (
    "tenant_id",
    "merchant_scope",
    "role",
    "risk_level",
    "doc_type",
    "effective_at",
    "policy_scope",
    "knowledge_scope",
)

_OUT_OF_DOMAIN_TERMS = ("银行卡", "绑定手机号", "登录密码", "天气", "股票")
_UNSAFE_QUERY_TERMS = ("ignore previous instructions", "忽略之前", "泄露", "系统提示", "私钥")
_DOMAIN_ANCHORS = (
    "补偿",
    "审批",
    "订单",
    "客服",
    "商家",
    "商品",
    "售后",
    "投诉",
    "物流",
    "申诉",
    "质量",
    "退款",
    "退货",
    "运费",
    "跨境",
    "证据",
    "争议",
    "政策",
)
_SPECIFIC_MARKERS = ("ORD-", "RF-", "跨境订单")
_ALIAS_EXPANSIONS: tuple[tuple[str, str, RewriteSource], ...] = (
    ("仅退款", "仅退款 商家举证 物流状态", "domain_synonym"),
    ("已发货", "商家已发货 物流核实", "merchant_support_alias"),
    ("补偿券", "补偿券 审批 材料", "domain_synonym"),
    ("七天无理由", "七天无理由 二次销售 退货退款", "intent_normalization"),
    ("退款时效", "退款时效 支付通道 超时", "intent_normalization"),
)


def build_query_rewrite_plan(
    query: str,
    context: KnowledgeContext | None,
    *,
    enabled: bool = True,
) -> QueryRewritePlan:
    original_query = str(query or "")

    if not enabled:
        return _skip_plan(original_query, "disabled")
    if not _has_required_trusted_context(context):
        return _skip_plan(original_query, "missing_trusted_context")
    if _contains_any(original_query, _UNSAFE_QUERY_TERMS, case_sensitive=False):
        return _skip_plan(original_query, "unsafe_query")
    if _contains_any(original_query, _OUT_OF_DOMAIN_TERMS):
        return _skip_plan(original_query, "out_of_domain")

    expansions = _build_expansions(original_query)
    if expansions:
        if len(expansions) > MAX_REWRITE_QUERIES:
            expansions = expansions[:MAX_REWRITE_QUERIES]
        trigger_terms = tuple(term for expansion in expansions for term in expansion.matched_terms)
        plan = QueryRewritePlan(
            original_query=original_query,
            rewritten_queries=tuple(expansion.query for expansion in expansions),
            expansions=tuple(expansions),
            trigger_terms=_dedupe(trigger_terms),
        )
        return plan.model_copy(update={"safe_summary": safe_rewrite_summary(plan)})

    if _is_already_specific(original_query):
        return _skip_plan(original_query, "already_specific")
    if not _contains_any(original_query, _DOMAIN_ANCHORS):
        return _skip_plan(original_query, "out_of_domain")

    return _skip_plan(original_query, "already_specific")


def safe_rewrite_summary(plan: QueryRewritePlan) -> str | None:
    if plan.skip_reason is not None:
        summary = f"{plan.source}: skip_reason={plan.skip_reason}; rewrite_count=0"
    else:
        triggers = ",".join(_dedupe(plan.trigger_terms))
        summary = f"{plan.source}: rewrite_count={len(plan.rewritten_queries)}; triggers={triggers}"
    return summary[:MAX_REWRITE_QUERY_CHARS]


def _skip_plan(original_query: str, reason: RewriteSkipReason) -> QueryRewritePlan:
    plan = QueryRewritePlan(original_query=original_query, skip_reason=reason)
    return plan.model_copy(update={"safe_summary": safe_rewrite_summary(plan)})


def _has_required_trusted_context(context: KnowledgeContext | None) -> bool:
    if context is None:
        return False
    tenant_value = getattr(context, f"{'tenant'}_{'id'}", None)
    merchant_value = getattr(context, f"{'merchant'}_{'scope'}", None)
    return bool(tenant_value) and bool(merchant_value)


def _build_expansions(query: str) -> list[RewriteExpansion]:
    expansions: list[RewriteExpansion] = []
    seen_queries: set[str] = set()
    for trigger, rewrite_query, source in _ALIAS_EXPANSIONS:
        if trigger not in query:
            continue
        bounded_query = rewrite_query[:MAX_REWRITE_QUERY_CHARS]
        if bounded_query in seen_queries:
            continue
        seen_queries.add(bounded_query)
        expansions.append(RewriteExpansion(query=bounded_query, source=source, matched_terms=(trigger,)))
    return expansions


def _is_already_specific(query: str) -> bool:
    normalized = query.upper()
    return any(marker in normalized for marker in _SPECIFIC_MARKERS)


def _contains_any(query: str, terms: tuple[str, ...], *, case_sensitive: bool = True) -> bool:
    if case_sensitive:
        return any(term in query for term in terms)
    lowered = query.lower()
    return any(term.lower() in lowered for term in terms)


def _dedupe(values: tuple[str, ...]) -> tuple[str, ...]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return tuple(ordered)
