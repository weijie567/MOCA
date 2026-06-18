from __future__ import annotations

from src.rag.chunker import chunk_markdown
from src.rag.search_text import build_policy_chunk_search_text
from tests.rag.phase21_xfail_inventory import xfail_for


@xfail_for("21-02-01/chunk-provenance")
def test_block_chunker_preserves_policy_chunk_content_and_ordered_source_block_refs() -> None:
    from src.rag.chunker import chunk_blocks

    blocks = [
        {
            "source_block_id": "block-001",
            "block_type": "heading",
            "text": "退款时效",
        },
        {
            "source_block_id": "block-002",
            "block_type": "paragraph",
            "text": "退款审核通过后，系统应在两个工作日内原路退回。",
        },
    ]

    chunks = chunk_blocks(blocks, doc_key="refund_policy")

    assert chunks[0].content == "退款时效\n退款审核通过后，系统应在两个工作日内原路退回。"
    assert chunks[0].source_block_refs_json == [
        {"source_block_id": "block-001", "block_index": 0},
        {"source_block_id": "block-002", "block_index": 1},
    ]


@xfail_for("21-02-01/table-chunking")
def test_table_chunker_preserves_headers_repeated_headers_and_merged_cell_metadata() -> None:
    from src.rag.chunker import chunk_blocks

    table_block = {
        "source_block_id": "table-001",
        "block_type": "table",
        "text": "场景 | 审核要求\n仅退款 | 核实物流\n仅退款 | 核实商家举证",
        "table_metadata": {
            "headers": ["场景", "审核要求"],
            "repeated_headers": True,
            "rows": [
                {"row_index": 1, "cells": ["仅退款", "核实物流"]},
                {
                    "row_index": 2,
                    "cells": ["仅退款", "核实商家举证"],
                    "merged_cells": [{"rowspan": 2, "colspan": 1, "text": "仅退款"}],
                },
            ],
        },
    }

    chunks = chunk_blocks([table_block], doc_key="refund_policy")

    assert "场景=仅退款" in chunks[0].content
    assert "审核要求=核实商家举证" in chunks[0].content
    assert chunks[0].table_context["repeated_headers"] is True
    assert chunks[0].table_context["merged_cells"][0]["rowspan"] == 2


def test_existing_markdown_chunker_keeps_policy_chunk_content_faithful() -> None:
    markdown = """
## 七天无理由
商品不影响二次销售时，支持七天无理由退货退款。
"""

    chunks = chunk_markdown(markdown, "refund_policy")

    assert chunks[0].section == "七天无理由"
    assert chunks[0].content == "商品不影响二次销售时，支持七天无理由退货退款。"


def test_search_text_enrichment_remains_retrieval_only_and_does_not_mutate_content() -> None:
    content = "商家举证成立时，客服应拒绝仅退款。"

    search_text = build_policy_chunk_search_text(
        title="退款规则",
        section="商家举证",
        content=content,
        doc_type="refund_rule",
        risk_level="high",
    )

    assert "退款规则" in search_text
    assert "商家举证" in search_text
    assert "refund_rule" in search_text
    assert content == "商家举证成立时，客服应拒绝仅退款。"

