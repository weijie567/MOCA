from __future__ import annotations

from pathlib import Path
from typing import Any

from src.rag.parsers.base import (
    ParsedBlock,
    ParseResult,
    ParserFailureCode,
    ParserWarning,
    normalize_block_text,
    safe_failed_result,
    sanitize_visible_text,
    synthetic_source_block_id,
)


PARSER_NAME = "moca_plain_text"
PARSER_VERSION = "21.01"


class PlainTextParserAdapter:
    source_type = "policy_plain_text"
    parser_name = PARSER_NAME
    parser_version = PARSER_VERSION
    supported_extensions = frozenset({".txt", ".text"})

    def parse(self, path: Path, *, doc_key: str, source_type: str, metadata: dict[str, Any]) -> ParseResult:
        try:
            raw_text = path.read_text(encoding=str(metadata.get("encoding", "utf-8")))
        except UnicodeDecodeError:
            return safe_failed_result(
                source_type=source_type,
                parser_name=self.parser_name,
                parser_version=self.parser_version,
                failure_code=ParserFailureCode.MALFORMED_SOURCE,
                safe_message="Policy plain-text source could not be decoded as text.",
            )
        except OSError:
            return safe_failed_result(
                source_type=source_type,
                parser_name=self.parser_name,
                parser_version=self.parser_version,
                failure_code=ParserFailureCode.MALFORMED_SOURCE,
                safe_message="Policy plain-text source could not be read.",
            )

        blocks = tuple(_iter_plain_text_blocks(raw_text, doc_key=doc_key, source_type=source_type))
        if not blocks:
            return ParseResult(
                status="failed",
                source_type=source_type,
                parser_name=self.parser_name,
                parser_version=self.parser_version,
                blocks=(),
                warnings=(ParserWarning(code="empty_source", message="No visible plain-text blocks were produced."),),
                failure_code=ParserFailureCode.MALFORMED_SOURCE.value,
                safe_message="Policy plain-text source did not contain visible text.",
            )

        warnings = tuple(warning for block in blocks for warning in block.warnings)
        return ParseResult(
            status="degraded" if warnings else "success",
            source_type=source_type,
            parser_name=self.parser_name,
            parser_version=self.parser_version,
            blocks=blocks,
            warnings=warnings,
            failure_code=None,
            safe_message=None,
        )


def _iter_plain_text_blocks(text: str, *, doc_key: str, source_type: str) -> list[ParsedBlock]:
    raw_blocks = [block for block in text.replace("\r\n", "\n").split("\n\n") if block.strip()]
    blocks: list[ParsedBlock] = []
    for raw_block in raw_blocks:
        block_index = len(blocks)
        sanitized, warnings = sanitize_visible_text(raw_block, block_index=block_index)
        if not sanitized:
            continue
        blocks.append(
            ParsedBlock(
                source_block_id=synthetic_source_block_id(
                    doc_key=doc_key,
                    source_type=source_type,
                    block_index=block_index,
                ),
                block_index=block_index,
                block_type="paragraph",
                text=sanitized,
                normalized_text=normalize_block_text(sanitized),
                source_type=source_type,
                parser_name=PARSER_NAME,
                parser_version=PARSER_VERSION,
                page_number=None,
                box=None,
                table_metadata={},
                ocr_metadata={},
                warnings=warnings,
            )
        )
    return blocks
