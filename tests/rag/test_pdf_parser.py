from __future__ import annotations

from tests.rag.phase21_xfail_inventory import xfail_for


@xfail_for("21-03-03/pdf-adapter")
def test_pdf_parser_emits_digital_text_blocks_with_page_local_source_boxes() -> None:
    from src.rag.parsers.pdf import PdfParser

    result = PdfParser().parse_bytes(b"%PDF digital text fixture", source_name="refund_policy.pdf")

    assert result.blocks[0].text == "七天无理由退货退款规则"
    assert result.blocks[0].source_box.page_number == 1
    assert result.blocks[0].source_box.coordinate_origin == "top_left"
    assert result.blocks[0].source_box.unit == "pdf_point"
    assert result.blocks[0].source_box.page_width > 0
    assert result.blocks[0].source_box.page_height > 0


@xfail_for("21-03-03/pdf-adapter")
def test_pdf_parser_preserves_table_row_cell_metadata() -> None:
    from src.rag.parsers.pdf import PdfParser

    result = PdfParser().parse_bytes(b"%PDF table fixture", source_name="refund_table.pdf")
    table = next(block for block in result.blocks if block.block_type == "table")

    assert table.table_metadata["headers"] == ["场景", "审核要求"]
    assert table.table_metadata["rows"][0]["cells"] == ["仅退款", "核实物流"]
    assert table.table_metadata["cells"][0]["row_index"] == 1
    assert table.table_metadata["cells"][0]["col_index"] == 0


@xfail_for("21-03-03/pdf-adapter")
def test_scanned_pdf_falls_back_to_ocr_with_rotation_when_known() -> None:
    from src.rag.parsers.pdf import PdfParser

    result = PdfParser().parse_bytes(b"%PDF scanned image fixture", source_name="scanned_refund.pdf")
    block = result.blocks[0]

    assert block.parser_metadata["scanned_page"] is True
    assert block.ocr_metadata["engine"] == "tesseract"
    assert block.ocr_metadata["language"] == "chi_sim+eng"
    assert block.source_box.unit == "pdf_point"
    assert block.source_box.rotation in (0, 90, 180, 270)

