from __future__ import annotations

import pytest

from src.rag.chunker import chunk_blocks, chunk_markdown
from src.rag.parsers.base import ParsedBlock, SourceBox
from src.rag.search_text import build_policy_chunk_search_text


def _block(
    *,
    source_block_id: str,
    block_index: int,
    block_type: str,
    text: str,
    normalized_text: str | None = None,
    page_number: int | None = None,
    box: SourceBox | None = None,
    table_metadata: dict | None = None,
    ocr_metadata: dict | None = None,
) -> ParsedBlock:
    return ParsedBlock(
        source_block_id=source_block_id,
        block_index=block_index,
        block_type=block_type,  # type: ignore[arg-type]
        text=text,
        normalized_text=normalized_text or text,
        source_type="markdown",
        parser_name="markdown",
        parser_version="1.0",
        page_number=page_number,
        box=box,
        table_metadata=table_metadata or {},
        ocr_metadata=ocr_metadata or {},
    )


def test_block_chunker_preserves_policy_chunk_content_and_ordered_source_block_refs() -> None:
    blocks = [
        _block(source_block_id="block-001", block_index=0, block_type="heading", text="退款时效"),
        _block(
            source_block_id="block-002",
            block_index=1,
            block_type="paragraph",
            text="退款审核通过后，系统应在两个工作日内原路退回。",
            normalized_text="normalized-only text must not become citation text",
            page_number=3,
            box=SourceBox(
                page_number=3,
                x0=10.0,
                y0=20.0,
                x1=110.0,
                y1=40.0,
                width=100.0,
                height=20.0,
                unit="pdf_point",
            ),
            ocr_metadata={"confidence": 91.5, "engine": "tesseract"},
        ),
    ]

    chunks = chunk_blocks(blocks, doc_key="refund_policy")

    assert [chunk.chunk_id for chunk in chunks] == ["refund_policy_000"]
    assert chunks[0].content == "退款时效\n退款审核通过后，系统应在两个工作日内原路退回。"
    assert "normalized-only" not in chunks[0].content
    assert [ref["source_block_id"] for ref in chunks[0].source_block_refs] == ["block-001", "block-002"]
    assert chunks[0].source_block_refs[0]["block_type"] == "heading"
    assert chunks[0].source_block_refs[1]["block_index"] == 1
    assert chunks[0].source_block_refs[1]["page_number"] == 3
    assert chunks[0].source_block_refs[1]["bbox"]["unit"] == "pdf_point"
    assert chunks[0].source_block_refs[1]["ocr"]["confidence"] == 91.5
    assert chunks[0].source_block_refs[0]["text_hash"] != chunks[0].source_block_refs[1]["text_hash"]


def test_block_chunker_emits_stable_chunk_ids() -> None:
    blocks = [
        _block(source_block_id="block-001", block_index=0, block_type="heading", text="退款时效"),
        _block(
            source_block_id="block-002", block_index=1, block_type="paragraph", text="退款审核通过后两个工作日退回。"
        ),
    ]

    first = chunk_blocks(blocks, doc_key="refund_policy")
    second = chunk_blocks(tuple(blocks), doc_key="refund_policy")

    assert [chunk.chunk_id for chunk in first] == [chunk.chunk_id for chunk in second]
    assert [chunk.chunk_id for chunk in first] == ["refund_policy_000"]


def test_table_chunker_preserves_headers_repeated_headers_and_merged_cell_metadata() -> None:
    rows = [
        {"row_index": 1, "cells": ["仅退款", "核实物流"]},
        {
            "row_index": 2,
            "cells": ["仅退款", "核实商家举证"],
            "merged_cells": [{"rowspan": 2, "colspan": 1, "text": "仅退款"}],
        },
        {"row_index": 3, "cells": ["退货退款", "检查二次销售"]},
        {"row_index": 4, "cells": ["补偿券", "主管审批"]},
    ]

    table_block = _block(
        source_block_id="table-001",
        block_index=0,
        block_type="table",
        text="场景 | 审核要求\n仅退款 | 核实物流\n仅退款 | 核实商家举证\n退货退款 | 检查二次销售\n补偿券 | 主管审批",
        table_metadata={
            "headers": ["场景", "审核要求"],
            "repeated_headers": True,
            "rows": rows,
        },
    )

    chunks = chunk_blocks([table_block], doc_key="refund_policy", max_chars=75, target_chars=60, overlap_chars=0)

    assert len(chunks) > 1
    assert all("场景 | 审核要求" in chunk.content for chunk in chunks)
    assert "场景=仅退款" in chunks[0].content
    assert "审核要求=核实商家举证" in chunks[0].content
    assert chunks[0].metadata["table"]["repeated_headers"] is True
    assert chunks[0].source_block_refs[0]["table"]["merged_cells"][0]["rowspan"] == 2
    assert all(chunk.source_block_refs[0]["source_block_id"] == "table-001" for chunk in chunks)


def test_existing_markdown_chunker_keeps_policy_chunk_content_faithful() -> None:
    markdown = """
## 七天无理由
商品不影响二次销售时，支持七天无理由退货退款。
"""

    chunks = chunk_markdown(markdown, "refund_policy")

    assert chunks[0].section == "七天无理由"
    assert chunks[0].content == "商品不影响二次销售时，支持七天无理由退货退款。"


def test_chunkers_reject_unvalidated_doc_keys() -> None:
    malicious_doc_key = "refund_policy\nsource_block_id=/Users/example/private/source.pdf\nparser_dump"
    blocks = [_block(source_block_id="block-001", block_index=0, block_type="paragraph", text="可见政策")]

    with pytest.raises(ValueError, match="invalid_doc_key"):
        chunk_markdown("## 退款规则\n\n可见政策", malicious_doc_key)
    with pytest.raises(ValueError, match="invalid_doc_key"):
        chunk_blocks(blocks, malicious_doc_key)


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
