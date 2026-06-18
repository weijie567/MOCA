from __future__ import annotations

from importlib import import_module

from src.knowledge.schemas import EvidenceRefV1
from tests.rag.phase21_xfail_inventory import xfail_for


@xfail_for("21-01-01/parser-registry")
def test_parser_registry_routes_only_allowlisted_policy_source_types() -> None:
    registry_module = import_module("src.rag.parsers.registry")

    registry = registry_module.ParserRegistry()

    assert registry.resolve("policy_markdown", ".md").source_type == "policy_markdown"
    assert registry.resolve("policy_pdf", ".pdf").source_type == "policy_pdf"
    assert registry.resolve("policy_docx", ".docx").source_type == "policy_docx"
    assert registry.resolve("policy_image", ".png").source_type == "policy_image"
    assert registry.resolve("business_order_export", ".csv") is None


@xfail_for("21-01-01/parser-dto")
def test_parse_result_exposes_project_owned_deterministic_output_fields() -> None:
    parser_base = import_module("src.rag.parsers.base")

    expected_names = {
        "ParseResult",
        "ParsedBlock",
        "SourceBox",
        "ParserWarning",
        "ParserFailureCode",
    }

    assert expected_names.issubset(set(dir(parser_base)))
    assert set(parser_base.ParseResult.__annotations__) >= {
        "source_type",
        "parser_name",
        "parser_version",
        "blocks",
        "warnings",
        "failure_code",
        "elapsed_ms",
    }
    assert set(parser_base.ParsedBlock.__annotations__) >= {
        "block_index",
        "block_type",
        "text",
        "normalized_text",
        "source_box",
        "parser_metadata",
        "ocr_metadata",
    }


@xfail_for("21-01-01/parser-failure-codes")
def test_parser_failure_codes_are_safe_and_finite() -> None:
    parser_base = import_module("src.rag.parsers.base")

    failure_codes = {item.value for item in parser_base.ParserFailureCode}

    assert {
        "unsupported_source_type",
        "signature_mismatch",
        "file_too_large",
        "too_many_pages",
        "image_too_large",
        "parser_timeout",
        "ocr_timeout",
        "malformed_source",
        "business_artifact_rejected",
    }.issubset(failure_codes)


def test_existing_evidence_ref_v1_has_no_parser_or_source_block_fields() -> None:
    fields = set(EvidenceRefV1.model_fields)

    assert not fields & {
        "page",
        "bbox",
        "source_box",
        "source_block_id",
        "source_block_refs_json",
        "parser_name",
        "parser_version",
        "parser_metadata_json",
        "ocr_confidence",
        "ocr_metadata_json",
        "ingestion_job_id",
    }

