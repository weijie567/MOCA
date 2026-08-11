from __future__ import annotations

import json
import unicodedata
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from src.rag.embedding_tokenizer import (
    EmbeddingTokenCounter,
    EmbeddingTokenizerError,
    EmbeddingTokenizerFailureCode,
    load_embedding_tokenizer_config,
)
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


@pytest.mark.parametrize(
    "source_text",
    [
        "退款审核通过后两个工作日内原路退回。" * 120,
        "Refund evidence must remain exact across deterministic rebuilds. " * 120,
        "Refund 退款 case A-1024 requires 人工复核." * 120,
        "OCR-like l0gistics 物流 2026/08/11 amount=128.50 CNY" * 120,
        "Cafe\u0301 与 café must preserve combining Unicode exactly." * 120,
        "Safe emoji sequence ✅🧾🔒👩\u200d💻" * 160,
        "https://example.invalid/rules/refund?v=4#evidence amount=123456.78" * 120,
    ],
    ids=["chinese", "english", "mixed", "ocr_like", "combining", "emoji", "url_numbers"],
)
def test_multilingual_and_adversarial_rebuilds_are_byte_identical_and_exactly_recounted(
    assembler: PolicyEmbeddingInputAssembler,
    counter: EmbeddingTokenCounter,
    source_text: str,
) -> None:
    block = _block(
        source_block_id="format:paragraph:0000",
        block_index=0,
        block_type="paragraph",
        text=source_text,
    )

    first = assembler.assemble(blocks=(block,), doc_key="format_policy", title="格式政策")
    second = assembler.assemble(blocks=(block,), doc_key="format_policy", title="格式政策")

    assert first == second
    assert "".join(item.primary_content for item in first) == source_text.strip()
    assert all(item.embedding_token_count == counter.count(item.embedding_input) for item in first)
    assert all(item.embedding_token_count <= counter.config.max_embedding_tokens for item in first)
    assert [item.embedding_input.encode("utf-8") for item in first] == [
        item.embedding_input.encode("utf-8") for item in second
    ]


def test_combining_marks_variation_selectors_and_zwj_sequences_are_not_split_at_unsafe_boundaries(
    assembler: PolicyEmbeddingInputAssembler,
) -> None:
    source_text = ("Cafe\u0301✅️👩\u200d💻退款" * 1_000).strip()
    block = _block(
        source_block_id="unicode:ocr:0000",
        block_index=0,
        block_type="ocr_text",
        text=source_text,
    )

    assembled = assembler.assemble(blocks=(block,), doc_key="unicode_policy", title="Unicode政策")

    assert "".join(item.primary_content for item in assembled) == source_text
    for item in assembled:
        assert not unicodedata.combining(item.primary_content[0])
        assert item.primary_content[0] not in {"\ufe0e", "\ufe0f", "\u200d"}
        assert not item.primary_content.endswith("\u200d")


def test_sentence_and_clause_splitting_preserves_exact_source_bytes_without_inserted_separators(
    assembler: PolicyEmbeddingInputAssembler,
) -> None:
    source_text = "第一句保持原样。第二句包含子句，仍不插入空白；Third clause stays exact!" * 180
    block = _block(
        source_block_id="sentence:paragraph:0000",
        block_index=0,
        block_type="paragraph",
        text=source_text,
    )

    assembled = assembler.assemble(blocks=(block,), doc_key="sentence_policy", title="句子政策")

    assert len(assembled) > 1
    assert "".join(item.primary_content for item in assembled) == source_text


def test_token_overlap_is_a_bounded_exact_suffix_charged_inside_every_final_input(
    assembler: PolicyEmbeddingInputAssembler,
    counter: EmbeddingTokenCounter,
) -> None:
    source_text = "退款审核需核实订单物流并记录结论。" * 300
    block = _block(
        source_block_id="overlap:paragraph:0000",
        block_index=0,
        block_type="paragraph",
        text=source_text,
    )

    assembled = assembler.assemble(blocks=(block,), doc_key="overlap_policy", title="退款政策")

    assert len(assembled) > 1
    assert any(item.overlap_content for item in assembled[1:])
    for previous, current in zip(assembled[:-1], assembled[1:], strict=True):
        assert current.overlap_content
        assert previous.primary_content.endswith(current.overlap_content)
        assert current.citation_content == f"{current.overlap_content}\n{current.primary_content}"
        assert current.overlap_token_count == counter.count(current.overlap_content)
        assert current.overlap_token_count <= counter.config.overlap_tokens
        assert current.embedding_token_count == counter.count(current.embedding_input)
        assert current.embedding_token_count <= counter.config.max_embedding_tokens


def test_oversized_table_cell_is_split_without_losing_header_row_or_provenance(
    assembler: PolicyEmbeddingInputAssembler,
    counter: EmbeddingTokenCounter,
) -> None:
    oversized_value = "超长单元格ABC123🙂" * 1_000
    table = _block(
        source_block_id="oversized:table:0000",
        block_index=0,
        block_type="table",
        text="表格原文",
        table_metadata={
            "headers": ["场景", "审核要求"],
            "repeated_headers": True,
            "rows": [{"row_index": 7, "cells": ["超长", oversized_value]}],
        },
    )

    assembled = assembler.assemble(blocks=(table,), doc_key="oversized_table", title="退款表格")

    header = "场景 | 审核要求\n"
    assert 1 < len(assembled) < 100
    assert all(item.primary_content.startswith(header) for item in assembled)
    assert "".join(item.primary_content.removeprefix(header) for item in assembled) == (
        f"场景=超长 | 审核要求={oversized_value}"
    )
    assert all(item.metadata["table"]["row_indices"] == (7,) for item in assembled)
    assert all(item.metadata["table"]["oversized_row_split"] is True for item in assembled)
    assert all(item.source_block_refs[0]["source_block_id"] == "oversized:table:0000" for item in assembled)
    assert all(counter.count(item.embedding_input) == item.embedding_token_count for item in assembled)
    assert all(item.embedding_token_count <= counter.config.max_embedding_tokens for item in assembled)


def test_oversized_table_header_fails_closed_instead_of_dropping_context(
    assembler: PolicyEmbeddingInputAssembler,
) -> None:
    table = _block(
        source_block_id="header:table:0000",
        block_index=0,
        block_type="table",
        text="表格原文",
        table_metadata={
            "headers": ["不得删除的超长表头" * 1_000, "审核要求"],
            "rows": [{"row_index": 0, "cells": ["场景", "规则"]}],
        },
    )

    with pytest.raises(PolicyEmbeddingInputError) as exc_info:
        assembler.assemble(blocks=(table,), doc_key="header_table", title="退款表格")

    assert exc_info.value.code is PolicyEmbeddingInputFailureCode.ENVELOPE_TOO_LARGE


def test_tokenizer_count_failure_propagates_before_any_dto_can_be_returned() -> None:
    counter = EmbeddingTokenCounter(load_embedding_tokenizer_config())

    class FailingTokenizer:
        def encode(self, text: str, *, add_special_tokens: bool) -> None:
            raise RuntimeError(f"private source must not leak: {text}")

    counter._tokenizer = FailingTokenizer()
    assembler = PolicyEmbeddingInputAssembler(counter=counter)
    block = _block(
        source_block_id="failure:paragraph:0000",
        block_index=0,
        block_type="paragraph",
        text="secret policy source",
    )

    with pytest.raises(EmbeddingTokenizerError) as exc_info:
        assembler.assemble(blocks=(block,), doc_key="failure_policy", title="Failure policy")

    assert exc_info.value.code is EmbeddingTokenizerFailureCode.COUNT_FAILED
    assert str(exc_info.value) == "count_failed"
    assert "secret" not in str(exc_info.value)


def test_count_probe_categories_remain_covered_by_assembler_properties() -> None:
    fixture_path = Path("evaluation/golden/embedding_tokenizer_count_probes.v1.json")
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))

    assert {probe["category"] for probe in payload["probes"]} == {
        "ascii",
        "chinese",
        "mixed",
        "markdown_table",
        "url",
        "numbers",
        "emoji",
        "unpunctuated_zh",
        "combining_unicode",
        "whitespace_envelope",
    }


def test_assembler_has_no_second_tokenizer_legacy_algorithm_or_character_budget_fallback() -> None:
    module_source = Path("src/rag/policy_embedding_input.py").read_text(encoding="utf-8")

    for forbidden in (
        "from tokenizers",
        "Tokenizer.from_file",
        "chunk_markdown",
        "_split_oversized",
        "max_chars",
        "target_chars",
        "overlap_chars",
    ):
        assert forbidden not in module_source
    assert "EmbeddingTokenCounter" in module_source
