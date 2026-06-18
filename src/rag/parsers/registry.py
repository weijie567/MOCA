from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from src.rag.parsers.base import ParseResult, ParserFailureCode, safe_failed_result
from src.rag.parsers.markdown import MarkdownParserAdapter
from src.rag.parsers.plain_text import PlainTextParserAdapter
from src.rag.parsers.safety import POLICY_SOURCE_TYPES, reject_business_artifact_source


@dataclass(frozen=True)
class ParserRoute:
    source_type: str
    extensions: frozenset[str]


class ParserAdapter(Protocol):
    source_type: str
    parser_name: str
    parser_version: str
    supported_extensions: frozenset[str]

    def parse(self, path: Path, *, doc_key: str, source_type: str, metadata: dict[str, Any]) -> ParseResult: ...


_ROUTES: dict[str, ParserRoute] = {
    "policy_markdown": ParserRoute("policy_markdown", frozenset({".md", ".markdown"})),
    "policy_plain_text": ParserRoute("policy_plain_text", frozenset({".txt", ".text"})),
    "policy_text": ParserRoute("policy_plain_text", frozenset({".txt", ".text"})),
    "policy_pdf": ParserRoute("policy_pdf", frozenset({".pdf"})),
    "policy_docx": ParserRoute("policy_docx", frozenset({".docx"})),
    "policy_image": ParserRoute("policy_image", frozenset({".png", ".jpg", ".jpeg", ".tif", ".tiff"})),
}


class ParserRegistry:
    def __init__(self, *, register_default_adapters: bool = True) -> None:
        self._adapters: dict[str, ParserAdapter] = {}
        if register_default_adapters:
            self.register("policy_markdown", MarkdownParserAdapter())
            self.register("policy_plain_text", PlainTextParserAdapter())
            self.register("policy_text", PlainTextParserAdapter())
            self._register_native_adapters()

    def register(self, source_type: str, adapter: ParserAdapter) -> None:
        route = _ROUTES.get(source_type)
        if route is None or route.source_type not in POLICY_SOURCE_TYPES:
            raise ValueError(f"Unsupported parser source_type: {source_type}")
        self._adapters[route.source_type] = adapter

    def resolve(self, source_type: str, extension: str) -> ParserRoute | None:
        if reject_business_artifact_source(source_type, {}) is not None:
            return None
        route = _ROUTES.get(source_type)
        if route is None:
            return None
        normalized_extension = extension.lower()
        if normalized_extension not in route.extensions:
            return None
        return route

    def parse(self, path: Path, *, doc_key: str, source_type: str, metadata: dict[str, Any]) -> ParseResult:
        business_failure = reject_business_artifact_source(source_type, metadata)
        if business_failure:
            return safe_failed_result(
                source_type=source_type,
                parser_name="moca_parser_registry",
                parser_version="21.01",
                failure_code=business_failure,
                safe_message="Business artifacts cannot be ingested as policy sources.",
            )

        route = self.resolve(source_type, path.suffix)
        if route is None:
            return safe_failed_result(
                source_type=source_type,
                parser_name="moca_parser_registry",
                parser_version="21.01",
                failure_code=ParserFailureCode.UNSUPPORTED_SOURCE_TYPE,
                safe_message="Unsupported policy source type or file extension.",
            )

        adapter = self._adapters.get(route.source_type)
        if adapter is None:
            return safe_failed_result(
                source_type=route.source_type,
                parser_name="moca_parser_registry",
                parser_version="21.01",
                failure_code=ParserFailureCode.UNSUPPORTED_SOURCE_TYPE,
                safe_message="No parser adapter is registered for this policy source type.",
            )

        return adapter.parse(path, doc_key=doc_key, source_type=route.source_type, metadata=metadata)

    def _register_native_adapters(self) -> None:
        from src.rag.parsers.docx import DocxParser
        from src.rag.parsers.image import ImageOcrParser
        from src.rag.parsers.pdf import PdfParser

        self.register("policy_pdf", PdfParser())
        self.register("policy_docx", DocxParser())
        self.register("policy_image", ImageOcrParser())
