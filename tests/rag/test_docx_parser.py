from __future__ import annotations

from tests.rag.phase21_xfail_inventory import xfail_for


@xfail_for("21-03-03/docx-adapter")
def test_docx_parser_emits_headings_paragraphs_and_tables_in_document_order() -> None:
    from src.rag.parsers.docx import DocxParser

    result = DocxParser().parse_bytes(b"docx fixture bytes", source_name="refund_policy.docx")

    assert [block.block_type for block in result.blocks[:4]] == [
        "heading",
        "paragraph",
        "table",
        "paragraph",
    ]
    assert [block.block_index for block in result.blocks[:4]] == [0, 1, 2, 3]
    assert result.blocks[0].text == "售后退款规则"


@xfail_for("21-03-03/docx-adapter")
def test_docx_parser_preserves_table_context_without_fabricating_page_or_bbox() -> None:
    from src.rag.parsers.docx import DocxParser

    result = DocxParser().parse_bytes(b"docx table fixture bytes", source_name="refund_table.docx")
    table = next(block for block in result.blocks if block.block_type == "table")

    assert table.table_metadata["headers"] == ["场景", "处理要求"]
    assert table.table_metadata["rows"][0]["cells"] == ["仅退款", "先核实物流"]
    assert table.source_box is None
    assert "page_number" not in table.parser_metadata
    assert "bbox" not in table.parser_metadata

