from __future__ import annotations

from src.rag.search_text import (
    DOMAIN_TERMS,
    build_policy_chunk_search_text,
    build_sparse_query_text,
    tokenize_search_text,
)


def test_domain_terms_are_preserved_as_tokens() -> None:
    tokens = tokenize_search_text("商家举证后，支持仅退款；七天无理由需要不影响二次销售。")

    assert "商家举证" in tokens
    assert "仅退款" in tokens
    assert "七天无理由" in tokens
    assert "二次销售" in tokens
    assert {"仅退款", "七天无理由", "二次销售", "商家举证"}.issubset(set(DOMAIN_TERMS))


def test_cjk_ngrams_and_ascii_terms_are_deterministic() -> None:
    first = tokenize_search_text("Refund SLA: 退款时效 48H")
    second = tokenize_search_text("Refund   SLA:\n退款时效 48h")

    assert first == second
    assert "refund" in first
    assert "sla" in first
    assert "48h" in first
    assert "退款时效" in first
    assert "退款" in first


def test_tokens_follow_first_seen_order_across_token_types() -> None:
    tokens = tokenize_search_text("Refund 仅退款 SLA")

    assert tokens.index("refund") < tokens.index("仅退款") < tokens.index("sla")


def test_build_policy_chunk_search_text_includes_context_without_mutating_content() -> None:
    content = "商品不影响二次销售时，客服可支持七天无理由退货退款。"

    search_text = build_policy_chunk_search_text(
        title="退款规则",
        section="七天无理由",
        content=content,
        doc_type="refund_rule",
        risk_level="high",
    )

    assert "退款规则" in search_text
    assert "七天无理由" in search_text
    assert "二次销售" in search_text
    assert "refund_rule" in search_text
    assert "high" in search_text
    assert content == "商品不影响二次销售时，客服可支持七天无理由退货退款。"


def test_build_policy_chunk_search_text_accepts_retrieval_only_block_context() -> None:
    content = "客服应先核实物流状态。"

    search_text = build_policy_chunk_search_text(
        title="退款规则",
        section="仅退款",
        content=content,
        doc_type="refund_rule",
        risk_level="medium",
        heading_path=("退款规则", "仅退款已发货"),
        table_headers=("场景", "审核要求"),
        source_context=("source_block_id=block-001", "page=2"),
    )

    assert "仅退款已发货" in search_text
    assert "场景" in search_text
    assert "source_block_id=block-001" in search_text
    assert content == "客服应先核实物流状态。"


def test_build_sparse_query_text_uses_bounded_or_terms_for_chinese_query() -> None:
    query_text = build_sparse_query_text("商家已发货还能仅退款吗")

    assert " | " in query_text
    assert "商家" in query_text
    assert "已发货" in query_text
    assert "仅退款" in query_text
    assert "商家已发货还能仅退款吗" not in query_text
    assert "退款吗" not in query_text
