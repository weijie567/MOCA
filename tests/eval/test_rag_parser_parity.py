from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import pytest

from src.rag.evaluation.contracts import (
    FormatParityDataset,
    FormatParityPolicy,
    FormatParityVariant,
    load_format_parity_contract,
)
from src.rag.evaluation.parser_parity import (
    comparison_text_contains,
    score_parser_result,
)
from src.rag.parsers.base import ParseResult, ParsedBlock, ParserWarning, SourceBox


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = REPOSITORY_ROOT / "evaluation/rag_sources/format_parity_manifest.jsonl"
GOLD_PATH = REPOSITORY_ROOT / "evaluation/golden/rag_format_parity_gold.json"


@pytest.fixture(scope="module")
def parity_dataset() -> FormatParityDataset:
    return load_format_parity_contract(MANIFEST_PATH, GOLD_PATH, repository_root=REPOSITORY_ROOT)


def _source_box(page_number: int) -> SourceBox:
    return SourceBox(
        page_number=page_number,
        x0=10.0,
        y0=20.0,
        x1=200.0,
        y1=40.0,
        width=595.0,
        height=842.0,
        unit="pdf_point",
    )


def _block(
    *,
    block_index: int,
    block_type: str,
    text: str,
    page_number: int | None,
    with_box: bool = True,
    scanned: bool = False,
    table_metadata: dict[str, object] | None = None,
    ocr_metadata: dict[str, object] | None = None,
) -> ParsedBlock:
    metadata = dict(ocr_metadata or {})
    if scanned and not metadata:
        metadata = {
            "engine": "tesseract",
            "engine_version": "5.5.0",
            "language": "chi_sim+eng",
            "average_confidence": 92.5,
            "confidence_status": "accepted",
            "low_confidence_word_count": 0,
            "timeout": False,
            "word_boxes": [{"raw_payload": "must-not-leak"}],
        }
    return ParsedBlock(
        source_block_id=f"source:block:{block_index:04d}",
        block_index=block_index,
        block_type=block_type,  # type: ignore[arg-type]
        text=text,
        normalized_text=" ".join(text.split()),
        source_type="policy_pdf" if page_number is not None else "policy_markdown",
        parser_name="fixture_parser",
        parser_version="1.0",
        page_number=page_number,
        box=_source_box(page_number) if page_number is not None and with_box else None,
        table_metadata=dict(table_metadata or {}),
        ocr_metadata=metadata,
    )


def _complete_result(policy: FormatParityPolicy, variant: FormatParityVariant) -> ParseResult:
    scanned = variant.format == "scanned_pdf"
    blocks: list[ParsedBlock] = []
    for index, anchor in enumerate(policy.gold.anchors):
        block_type = {
            "heading": "heading",
            "table_header": "table",
            "table_row": "table",
        }.get(anchor.kind, "paragraph")
        page_number = None if variant.format == "markdown" else (index % int(variant.pages or 1)) + 1
        table_metadata: dict[str, object] = {}
        if anchor.kind == "table_header":
            table_metadata = {"headers": anchor.text.split()}
        elif anchor.kind == "table_row":
            table_metadata = {"rows": [{"cells": anchor.text.split()}]}
        blocks.append(
            _block(
                block_index=index,
                block_type=block_type,
                text=anchor.text,
                page_number=page_number,
                scanned=scanned,
                table_metadata=table_metadata,
            )
        )
    if variant.pages:
        covered_pages = {block.page_number for block in blocks}
        for page_number in range(1, variant.pages + 1):
            if page_number not in covered_pages:
                blocks.append(
                    _block(
                        block_index=len(blocks),
                        block_type="paragraph",
                        text=f"page {page_number} visible text",
                        page_number=page_number,
                        scanned=scanned,
                    )
                )
    return ParseResult(
        status="success",
        source_type=variant.source_type,
        parser_name="fixture_parser",
        parser_version="1.0",
        blocks=tuple(blocks),
        warnings=(),
        failure_code=None,
        safe_message=None,
    )


def _policy_and_variant(
    dataset: FormatParityDataset,
    *,
    variant_name: str,
) -> tuple[FormatParityPolicy, FormatParityVariant]:
    policy = dataset.policies[0]
    variant = next(item for item in policy.variants if item.format == variant_name)
    return policy, variant


def test_scores_every_parser_dimension_independently_with_real_dtos(
    parity_dataset: FormatParityDataset,
) -> None:
    policy, variant = _policy_and_variant(parity_dataset, variant_name="digital_pdf")

    result = score_parser_result(policy=policy, variant=variant, parse_result=_complete_result(policy, variant))

    assert result.parse_status.status == "passed"
    assert result.semantic_anchors.status == "passed"
    assert result.heading_structure.status == "passed"
    assert result.critical_tables.status == "passed"
    assert result.provenance_locators.status == "passed"
    assert result.pdf_page_coverage.status == "passed"
    assert result.ocr_diagnostics.status == "not_applicable"
    assert result.warning_failures.status == "passed"
    assert result.semantic_anchors.expected == len(policy.gold.anchors)
    assert result.heading_structure.expected == sum(anchor.kind == "heading" for anchor in policy.gold.anchors)
    assert result.critical_tables.expected == sum(
        anchor.kind in {"table_header", "table_row"} for anchor in policy.gold.anchors
    )


@pytest.mark.parametrize(
    ("mutation", "failed_dimension", "unaffected_dimension"),
    [
        ("anchor", "semantic_anchors", "heading_structure"),
        ("heading", "heading_structure", "semantic_anchors"),
        ("table", "critical_tables", "semantic_anchors"),
        ("locator", "provenance_locators", "semantic_anchors"),
        ("page", "pdf_page_coverage", "semantic_anchors"),
    ],
)
def test_one_dimension_failure_does_not_erase_other_scores(
    parity_dataset: FormatParityDataset,
    mutation: str,
    failed_dimension: str,
    unaffected_dimension: str,
) -> None:
    policy, variant = _policy_and_variant(parity_dataset, variant_name="digital_pdf")
    complete = _complete_result(policy, variant)
    blocks = list(complete.blocks)

    if mutation == "anchor":
        fact_index = next(index for index, anchor in enumerate(policy.gold.anchors) if anchor.kind == "fact")
        blocks[fact_index] = replace(
            blocks[fact_index],
            text="unrelated visible policy text",
            normalized_text="unrelated visible policy text",
        )
    elif mutation == "heading":
        heading_index = next(index for index, anchor in enumerate(policy.gold.anchors) if anchor.kind == "heading")
        blocks[heading_index] = replace(blocks[heading_index], block_type="paragraph")
    elif mutation == "table":
        table_index = next(index for index, anchor in enumerate(policy.gold.anchors) if anchor.kind == "table_header")
        blocks[table_index] = replace(blocks[table_index], block_type="paragraph", table_metadata={})
    elif mutation == "locator":
        blocks = [replace(block, box=None) for block in blocks]
    else:
        blocks = [
            replace(block, page_number=1, box=_source_box(1)) if block.page_number == variant.pages else block
            for block in blocks
        ]

    result = score_parser_result(
        policy=policy,
        variant=variant,
        parse_result=replace(complete, blocks=tuple(blocks)),
    )

    assert getattr(result, failed_dimension).status == "failed"
    assert getattr(result, unaffected_dimension).status == "passed"


def test_scanned_pdf_empty_garbled_and_zero_anchor_output_are_ocr_quality_failures(
    parity_dataset: FormatParityDataset,
) -> None:
    policy, variant = _policy_and_variant(parity_dataset, variant_name="scanned_pdf")
    cases = (
        ParseResult(
            status="degraded",
            source_type="policy_pdf",
            parser_name="fixture_parser",
            parser_version="1.0",
            blocks=(),
            warnings=(),
            failure_code=None,
            safe_message="OCR completed without visible text.",
        ),
        ParseResult(
            status="degraded",
            source_type="policy_pdf",
            parser_name="fixture_parser",
            parser_version="1.0",
            blocks=(
                _block(
                    block_index=0,
                    block_type="ocr_text",
                    text="##@@@ garbled OCR output",
                    page_number=1,
                    scanned=True,
                    ocr_metadata={
                        "engine": "tesseract",
                        "engine_version": "5.5.0",
                        "language": "chi_sim+eng",
                        "average_confidence": 2.0,
                        "confidence_status": "review_required",
                    },
                ),
            ),
            warnings=(),
            failure_code=None,
            safe_message=None,
        ),
    )

    for parse_result in cases:
        scored = score_parser_result(policy=policy, variant=variant, parse_result=parse_result)
        assert scored.outcome == "completed_quality_fail"
        assert scored.ocr_diagnostics.status == "failed"
        assert any(
            observation.primary_stage == "ocr" and observation.status == "missed" for observation in scored.observations
        )


def test_warning_and_failure_codes_are_scored_without_hiding_other_dimensions(
    parity_dataset: FormatParityDataset,
) -> None:
    policy, variant = _policy_and_variant(parity_dataset, variant_name="markdown")
    complete = _complete_result(policy, variant)
    warning = ParserWarning(code="text_truncated", message="Parser text was truncated.")
    degraded = replace(complete, status="degraded", warnings=(warning,))

    result = score_parser_result(policy=policy, variant=variant, parse_result=degraded)

    assert result.parse_status.status == "failed"
    assert result.warning_failures.status == "failed"
    assert result.warning_failures.reason_codes == ("parse_status_degraded", "warning:text_truncated")
    assert result.semantic_anchors.status == "passed"


def test_comparison_normalization_preserves_protected_policy_meaning() -> None:
    protected = "Policy ID RG-2026-08 不得自动退款 2026-08-10 23:59 退款比例 10% 至 30%"

    assert comparison_text_contains(
        protected,
        "Policy\u00a0ID RG-2026-08\n不得自动退款 2026-08-10  23:59 退款比例 10%\t至 30%",
        allow_ocr_layout=True,
    )
    for changed in (
        protected.replace("RG-2026-08", "RG-2026-09"),
        protected.replace("不得", "可以"),
        protected.replace("2026-08-10", "2026-08-11"),
        protected.replace("23:59", "23:58"),
        protected.replace("10%", "20%"),
        protected.replace("30%", "35%"),
    ):
        assert not comparison_text_contains(protected, changed, allow_ocr_layout=True)

    assert comparison_text_contains(
        "场景 默认处理 金额基准 需要补充的证据",
        "场景 | 默认处理 | 金额基准 | 需要补充的证据",
        allow_ocr_layout=False,
    )
    assert not comparison_text_contains(
        "场景 默认处理 金额基准 需要补充的证据",
        "场景 | 自动通过 | 金额基准 | 需要补充的证据",
        allow_ocr_layout=False,
    )


def test_scoring_does_not_mutate_parse_result_or_nested_metadata(
    parity_dataset: FormatParityDataset,
) -> None:
    policy, variant = _policy_and_variant(parity_dataset, variant_name="scanned_pdf")
    parse_result = _complete_result(policy, variant)
    before = deepcopy(parse_result)

    score_parser_result(policy=policy, variant=variant, parse_result=parse_result)

    assert parse_result == before
    assert parse_result.blocks[0].text == before.blocks[0].text
    assert parse_result.blocks[0].normalized_text == before.blocks[0].normalized_text
    assert parse_result.blocks[0].ocr_metadata == before.blocks[0].ocr_metadata


def test_serialized_diagnostics_are_bounded_allowlisted_and_safe(
    parity_dataset: FormatParityDataset,
) -> None:
    policy, variant = _policy_and_variant(parity_dataset, variant_name="scanned_pdf")
    hostile = ParseResult(
        status="failed",
        source_type="policy_pdf",
        parser_name="fixture_parser",
        parser_version="1.0",
        blocks=(),
        warnings=(
            ParserWarning(
                code="parser_exception_sanitized",
                message="Traceback /Users/alice/private.pdf raw_payload=" + "x" * 500,
            ),
        ),
        failure_code="malformed_source",
        safe_message="Traceback /private/tmp/private.pdf parser_dump=" + "y" * 500,
    )

    result = score_parser_result(policy=policy, variant=variant, parse_result=hostile)
    payload = result.model_dump(mode="json")
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    serialized_snippets = json.dumps(
        [item["safe_snippet"] for item in payload["safe_diagnostics"]],
        ensure_ascii=False,
        sort_keys=True,
    )

    assert len(result.safe_diagnostics[0].safe_snippet or "") <= 160
    for forbidden in (
        "/Users/",
        "/private/tmp/",
        "Traceback",
        "raw_payload",
        "parser_dump",
        "word_boxes",
        "arbitrary_metadata",
        "stack_trace",
        "file_path",
    ):
        assert forbidden not in serialized
    assert "exception" not in serialized_snippets


def test_scoring_is_byte_equivalent_for_identical_dtos_and_clock(
    parity_dataset: FormatParityDataset,
) -> None:
    policy, variant = _policy_and_variant(parity_dataset, variant_name="scanned_pdf")
    parse_result = _complete_result(policy, variant)

    first = score_parser_result(policy=policy, variant=variant, parse_result=parse_result)
    second = score_parser_result(policy=policy, variant=variant, parse_result=parse_result)

    assert first.model_dump_json() == second.model_dump_json()
    assert [
        (item.policy_id, item.variant, item.case_id, item.anchor_id, item.reason_code) for item in first.observations
    ] == sorted(
        (
            item.policy_id,
            item.variant,
            item.case_id,
            item.anchor_id,
            item.reason_code,
        )
        for item in first.observations
    )
