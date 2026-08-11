from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from src.rag.embedding_tokenizer import EmbeddingTokenCounter, load_embedding_tokenizer_config
from src.rag.parsers.base import ParsedBlock
from src.rag.policy_embedding_input import (
    PolicyEmbeddingInputAssembler,
    PolicyEmbeddingInputFailureCode,
    PolicyEmbeddingInputError,
)


def _block(
    *,
    source_block_id: str,
    block_index: int,
    block_type: str,
    text: str,
    table_metadata: dict | None = None,
    ocr_metadata: dict | None = None,
) -> ParsedBlock:
    return ParsedBlock(
        source_block_id=source_block_id,
        block_index=block_index,
        block_type=block_type,  # type: ignore[arg-type]
        text=text,
        normalized_text=text,
        source_type="policy_markdown",
        parser_name="markdown",
        parser_version="21.01",
        page_number=block_index + 1,
        box=None,
        table_metadata=table_metadata or {},
        ocr_metadata=ocr_metadata or {},
    )


@pytest.fixture(scope="module")
def counter() -> EmbeddingTokenCounter:
    return EmbeddingTokenCounter(load_embedding_tokenizer_config())


@pytest.fixture(scope="module")
def assembler(counter: EmbeddingTokenCounter) -> PolicyEmbeddingInputAssembler:
    return PolicyEmbeddingInputAssembler(counter=counter)


def test_assembler_returns_one_immutable_exact_final_input_dto(
    assembler: PolicyEmbeddingInputAssembler,
    counter: EmbeddingTokenCounter,
) -> None:
    blocks = (
        _block(source_block_id="refund:heading:0000", block_index=0, block_type="heading", text="退款时效"),
        _block(
            source_block_id="refund:paragraph:0001",
            block_index=1,
            block_type="paragraph",
            text="退款审核通过后，系统应在两个工作日内原路退回。",
            ocr_metadata={"confidence": 93.5, "engine": "fixture"},
        ),
    )

    assembled = assembler.assemble(
        blocks=blocks,
        doc_key="refund_policy",
        title="退款政策",
        doc_type="refund_rule",
        risk_level="high",
    )

    assert len(assembled) == 1
    item = assembled[0]
    assert item.chunk_id == "refund_policy_000"
    assert item.section == "退款时效"
    assert item.citation_content == "退款时效\n退款审核通过后，系统应在两个工作日内原路退回。"
    assert item.primary_content == item.citation_content
    assert item.overlap_content == ""
    assert item.embedding_input == (
        "退款政策 / 退款时效: 退款时效\n退款审核通过后，系统应在两个工作日内原路退回。\n"
        "source_block_id=refund:heading:0000\n"
        "source_block_id=refund:paragraph:0001"
    )
    assert item.embedding_token_count == counter.count(item.embedding_input)
    assert item.embedding_token_count <= counter.config.max_embedding_tokens
    assert item.chunking_config_fingerprint == counter.config.config_fingerprint
    assert item.embedding_input_hash.startswith("sha256:")
    assert item.citation_content != item.search_text
    assert item.search_text != item.embedding_input
    assert "refund_rule" in item.search_text
    assert "high" in item.search_text
    assert [ref["source_block_id"] for ref in item.source_block_refs] == [
        "refund:heading:0000",
        "refund:paragraph:0001",
    ]
    assert item.source_block_refs[1]["ocr"]["confidence"] == 93.5
    with pytest.raises(FrozenInstanceError):
        item.embedding_token_count = 0  # type: ignore[misc]
    with pytest.raises(TypeError):
        item.source_block_refs[0]["source_block_id"] = "changed"  # type: ignore[index]


def test_assembler_groups_whole_blocks_to_target_then_splits_structurally(
    assembler: PolicyEmbeddingInputAssembler,
    counter: EmbeddingTokenCounter,
) -> None:
    paragraphs = [f"第{index}条：" + ("商家举证成立后再处理退款。" * 18) for index in range(8)]
    blocks = tuple(
        _block(
            source_block_id=f"refund:paragraph:{index:04d}",
            block_index=index,
            block_type="paragraph",
            text=text,
        )
        for index, text in enumerate(paragraphs)
    )

    assembled = assembler.assemble(blocks=blocks, doc_key="refund_policy", title="退款政策")

    assert len(assembled) > 1
    assert [item.chunk_index for item in assembled] == list(range(len(assembled)))
    assert all(item.embedding_token_count <= counter.config.max_embedding_tokens for item in assembled)
    assert all(counter.count(item.embedding_input) == item.embedding_token_count for item in assembled)
    assert "\n".join(item.primary_content for item in assembled) == "\n".join(paragraphs)
    assert all(item.source_block_refs for item in assembled)


def test_table_rows_and_headers_are_preserved_inside_the_exact_budget(
    assembler: PolicyEmbeddingInputAssembler,
    counter: EmbeddingTokenCounter,
) -> None:
    protected_url = "https://example.test/refunds/RF-20260811?amount=123456.78"
    rows = [
        {"row_index": index, "cells": [f"场景-{index}", f"审核要求-{index}-" + ("核验凭证" * 18)]}
        for index in range(12)
    ]
    rows[5] = {"row_index": 5, "cells": ["保护值", protected_url]}
    table = _block(
        source_block_id="refund:table:0000",
        block_index=0,
        block_type="table",
        text="表格原文",
        table_metadata={
            "headers": ["场景", "审核要求"],
            "repeated_headers": True,
            "rows": rows,
            "merged_cells": [{"rowspan": 2, "colspan": 1, "text": "场景-0"}],
        },
    )

    assembled = assembler.assemble(blocks=(table,), doc_key="refund_table", title="退款表格")

    assert len(assembled) > 1
    assert all(item.primary_content.startswith("场景 | 审核要求\n") for item in assembled)
    assert all(item.embedding_token_count <= counter.config.max_embedding_tokens for item in assembled)
    assert sum(protected_url in item.primary_content for item in assembled) == 1
    assert all(item.metadata["table"]["repeated_headers"] is True for item in assembled)
    assert all(item.metadata["table"]["row_indices"] for item in assembled)
    assert all(item.source_block_refs[0]["table"]["merged_cells"] for item in assembled)
    rendered_rows = [f"场景={row['cells'][0]} | 审核要求={row['cells'][1]}" for row in rows]
    for rendered_row in rendered_rows:
        assert sum(rendered_row in item.primary_content for item in assembled) == 1


def test_unpunctuated_oversized_unit_uses_bounded_token_windows_without_truncation(
    assembler: PolicyEmbeddingInputAssembler,
    counter: EmbeddingTokenCounter,
) -> None:
    unpunctuated = "退款规则ABC123🙂" * 1_000
    block = _block(
        source_block_id="refund:ocr:0000",
        block_index=0,
        block_type="ocr_text",
        text=unpunctuated,
        ocr_metadata={"confidence": 61.0},
    )

    assembled = assembler.assemble(blocks=(block,), doc_key="refund_ocr", title="OCR政策")

    assert 1 < len(assembled) < 100
    assert "".join(item.primary_content for item in assembled) == unpunctuated
    assert all(item.primary_content for item in assembled)
    assert all(item.embedding_token_count <= counter.config.max_embedding_tokens for item in assembled)
    assert all(item.source_block_refs[0]["source_block_id"] == "refund:ocr:0000" for item in assembled)


def test_empty_input_terminates_and_envelope_dominance_fails_closed(
    assembler: PolicyEmbeddingInputAssembler,
) -> None:
    assert assembler.assemble(blocks=(), doc_key="empty_policy", title="空政策") == ()
    whitespace = _block(
        source_block_id="empty:paragraph:0000",
        block_index=0,
        block_type="paragraph",
        text=" \n\t ",
    )
    assert assembler.assemble(blocks=(whitespace,), doc_key="empty_policy", title="空政策") == ()

    tiny = _block(
        source_block_id="dominant:paragraph:0000",
        block_index=0,
        block_type="paragraph",
        text="有效规则",
    )
    with pytest.raises(PolicyEmbeddingInputError) as exc_info:
        assembler.assemble(
            blocks=(tiny,),
            doc_key="dominant_policy",
            title="超长标题" * 1_000,
        )
    assert exc_info.value.code is PolicyEmbeddingInputFailureCode.ENVELOPE_TOO_LARGE
    assert str(exc_info.value) == "envelope_too_large"
    assert "超长标题" not in str(exc_info.value)
