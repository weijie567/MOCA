"""Persistence-free scoring for production parser parity results."""

from __future__ import annotations

import re
import shutil
import subprocess
import unicodedata
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import replace
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from src.rag.evaluation.contracts import (
    EvaluationOutcome,
    FormatParityDataset,
    FormatParityPolicy,
    FormatParityVariant,
    SemanticAnchor,
)
from src.rag.parsers.base import ParseResult, ParsedBlock, ParserWarning, safe_failed_result
from src.rag.parsers.registry import ParserRegistry


PARSER_PARITY_SCHEMA_VERSION = "parser_parity_variant.v1"
PARSER_PARITY_RUN_SCHEMA_VERSION = "parser_parity_run.v1"
PARSER_PARITY_COMMAND = "scripts/eval_rag_parser_parity.py"
SAFE_SNIPPET_MAX_CHARS = 160
_REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
_VARIANT_ORDER = {"markdown": 0, "digital_pdf": 1, "scanned_pdf": 2}
_OCR_UNAVAILABLE_CODES = frozenset(
    {
        "ocr_executable_unavailable",
        "ocr_language_unavailable",
        "ocr_runtime_unavailable",
        "ocr_traineddata_unavailable",
    }
)
_SAFE_CODE = re.compile(r"^[a-z0-9][a-z0-9_.:-]{0,127}$")
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_LOCAL_PATH = re.compile(r"(?:(?:file://)?/(?:Users|home|private|tmp|var|Volumes)/[^\s)>\]]+|[A-Za-z]:\\[^\s)>\]]+)")
_UNSAFE_DIAGNOSTIC = re.compile(
    r"(?:traceback|stack[_ -]?trace|parser[_ -]?dump|raw[_ -]?(?:bytes|payload|parser)|%PDF-)",
    re.IGNORECASE,
)
_TABLE_LAYOUT = re.compile(r"[|｜]+")
_WHITESPACE = re.compile(r"\s+")
_CJK_LAYOUT_WHITESPACE = re.compile(r"(?<=[\u3400-\u9fff])\s+(?=[\u3400-\u9fff])")

DimensionName = Literal[
    "parse_status",
    "semantic_anchors",
    "heading_structure",
    "critical_tables",
    "provenance_locators",
    "pdf_page_coverage",
    "ocr_diagnostics",
    "warning_failures",
]
DimensionStatus = Literal["passed", "failed", "not_applicable"]
ObservationStatus = Literal["matched", "missed"]
ParserPrimaryStage = Literal["parser", "ocr", "provenance"]
CaseStatus = Literal["passed", "failed", "not_applicable"]
ParserExecutionMode = Literal["parser_direct", "contract_test"]
PrerequisiteStatus = Literal["available", "unavailable", "not_required"]
RuntimeKind = Literal["parser", "ocr"]


class ParserDimensionV1(BaseModel):
    """One independently auditable parser-quality dimension."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    dimension: DimensionName
    status: DimensionStatus
    matched: int = Field(ge=0)
    expected: int = Field(ge=0)
    recall: float | None = Field(default=None, ge=0.0, le=1.0)
    reason_codes: tuple[str, ...] = ()


class ParserObservationV1(BaseModel):
    """Safe attribution for one semantic or locator expectation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    policy_id: str
    variant: Literal["markdown", "digital_pdf", "scanned_pdf"]
    case_id: str
    anchor_id: str
    anchor_kind: Literal["heading", "fact", "table_header", "table_row"]
    expected_locator_summary: str
    status: ObservationStatus
    primary_stage: ParserPrimaryStage
    reason_code: str


class SafeParserDiagnosticV1(BaseModel):
    """Bounded diagnostic projection that never contains raw parser payloads."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str
    block_index: int | None = None
    safe_snippet: str | None = Field(default=None, max_length=SAFE_SNIPPET_MAX_CHARS)


class ParserCaseResultV1(BaseModel):
    """Case-level parser attribution without query/answer or evidence text."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    policy_id: str
    variant: Literal["markdown", "digital_pdf", "scanned_pdf"]
    case_id: str
    category: Literal[
        "facts",
        "exceptions",
        "amounts_time_limits",
        "tables",
        "cross_section",
        "no_answer",
    ]
    status: CaseStatus
    matched_anchors: int = Field(ge=0)
    expected_anchors: int = Field(ge=0)
    anchor_recall: float | None = Field(default=None, ge=0.0, le=1.0)
    primary_stage: ParserPrimaryStage | None = None
    reason_codes: tuple[str, ...] = ()


class ParserVariantResultV1(BaseModel):
    """Stable intermediate result consumed by the all-fixture runner."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["parser_parity_variant.v1"] = PARSER_PARITY_SCHEMA_VERSION
    policy_id: str
    variant: Literal["markdown", "digital_pdf", "scanned_pdf"]
    source_type: str
    parser_name: str
    parser_version: str
    ocr_engine: str | None = None
    ocr_engine_version: str | None = None
    ocr_language: str | None = None
    outcome: EvaluationOutcome
    parse_status: ParserDimensionV1
    semantic_anchors: ParserDimensionV1
    heading_structure: ParserDimensionV1
    critical_tables: ParserDimensionV1
    provenance_locators: ParserDimensionV1
    pdf_page_coverage: ParserDimensionV1
    ocr_diagnostics: ParserDimensionV1
    warning_failures: ParserDimensionV1
    observations: tuple[ParserObservationV1, ...]
    case_results: tuple[ParserCaseResultV1, ...]
    safe_diagnostics: tuple[SafeParserDiagnosticV1, ...]


class FixtureHashV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    path: str
    sha256: str


class ParserParityInputsV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    manifest_hash: str
    gold_hash: str
    baseline_identity: str
    fixture_hashes: tuple[FixtureHashV1, ...]


class ParserPrerequisiteV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: Literal["persistence", "embedding_provider", "retrieval_runtime", "ocr_runtime"]
    status: PrerequisiteStatus
    reason_code: str
    version: str | None = None
    required_languages: tuple[str, ...] = ()


class ParserRuntimeVersionV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: RuntimeKind
    name: str
    version: str
    language: str | None = None


class ParserRunFailureV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    policy_id: str
    variant: Literal["markdown", "digital_pdf", "scanned_pdf"]
    primary_stage: ParserPrimaryStage
    reason_code: str


class ParserParityRunV1(BaseModel):
    """Canonical persistence-free result for all nine validated fixtures."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["parser_parity_run.v1"] = PARSER_PARITY_RUN_SCHEMA_VERSION
    command: Literal["scripts/eval_rag_parser_parity.py"] = PARSER_PARITY_COMMAND
    mode: ParserExecutionMode
    generated_at: str
    outcome: EvaluationOutcome
    inputs: ParserParityInputsV1
    prerequisites: tuple[ParserPrerequisiteV1, ...]
    runtime_versions: tuple[ParserRuntimeVersionV1, ...]
    variant_results: tuple[ParserVariantResultV1, ...]
    safe_failures: tuple[ParserRunFailureV1, ...]


def comparison_text_contains(
    expected: str,
    candidate: str,
    *,
    allow_ocr_layout: bool,
) -> bool:
    """Compare copied strings using layout-only normalization.

    The transformation never edits identifiers, digits, dates, percentages,
    negations, punctuation, or source DTO values. It only normalizes Unicode,
    table separators, and whitespace introduced by layout extraction/OCR.
    """

    expected_copy = _comparison_copy(expected, allow_ocr_layout=allow_ocr_layout)
    candidate_copy = _comparison_copy(candidate, allow_ocr_layout=allow_ocr_layout)
    return bool(expected_copy) and expected_copy in candidate_copy


def evaluate_parser_parity(
    dataset: FormatParityDataset,
    *,
    parser_registry: ParserRegistry | None = None,
    generated_at: str,
) -> ParserParityRunV1:
    """Run the exact validated 3x3 corpus through ``ParserRegistry.parse``."""

    registry = parser_registry or ParserRegistry()
    mode: ParserExecutionMode = "contract_test" if parser_registry is not None else "parser_direct"
    ocr_prerequisite = _detect_ocr_prerequisite()
    prerequisites = (
        ParserPrerequisiteV1(
            name="persistence",
            status="not_required",
            reason_code="parser_direct_has_no_persistence_dependency",
        ),
        ParserPrerequisiteV1(
            name="embedding_provider",
            status="not_required",
            reason_code="parser_direct_has_no_embedding_dependency",
        ),
        ParserPrerequisiteV1(
            name="retrieval_runtime",
            status="not_required",
            reason_code="parser_direct_has_no_retrieval_dependency",
        ),
        ocr_prerequisite,
    )

    results: list[ParserVariantResultV1] = []
    for policy in sorted(dataset.policies, key=lambda item: item.doc_key):
        for variant in sorted(policy.variants, key=lambda item: _VARIANT_ORDER[item.format]):
            parse_result = _parse_one_fixture(
                registry=registry,
                policy=policy,
                variant=variant,
            )
            scored = score_parser_result(policy=policy, variant=variant, parse_result=parse_result)
            if variant.format == "scanned_pdf" and ocr_prerequisite.status == "unavailable":
                scored = _with_unavailable_ocr(scored, reason_code=ocr_prerequisite.reason_code)
            results.append(scored)

    variant_results = tuple(
        sorted(
            results,
            key=lambda item: (item.policy_id, _VARIANT_ORDER[item.variant]),
        )
    )
    return ParserParityRunV1(
        mode=mode,
        generated_at=str(generated_at),
        outcome=_run_outcome(variant_results),
        inputs=ParserParityInputsV1(
            manifest_hash=dataset.manifest_hash,
            gold_hash=dataset.gold_hash,
            baseline_identity=dataset.baseline_identity,
            fixture_hashes=tuple(
                FixtureHashV1(path=path, sha256=digest) for path, digest in sorted(dataset.fixture_hashes.items())
            ),
        ),
        prerequisites=prerequisites,
        runtime_versions=_runtime_versions(variant_results, ocr_prerequisite=ocr_prerequisite),
        variant_results=variant_results,
        safe_failures=_run_failures(variant_results),
    )


def score_parser_result(
    *,
    policy: FormatParityPolicy,
    variant: FormatParityVariant,
    parse_result: ParseResult,
) -> ParserVariantResultV1:
    """Score one production ``ParseResult`` without mutating its DTO graph."""

    visible_blocks = tuple(block for block in parse_result.blocks if block.text.strip())
    allow_ocr_layout = variant.format == "scanned_pdf" or any(
        case.locator_constraints is not None and case.locator_constraints.ocr_whitespace_normalization
        for case in policy.gold.cases
    )

    anchor_matches = {
        anchor.anchor_id: _matching_blocks(
            anchor,
            visible_blocks,
            allow_ocr_layout=allow_ocr_layout,
            enforce_kind=False,
        )
        for anchor in policy.gold.anchors
    }
    heading_anchors = tuple(anchor for anchor in policy.gold.anchors if anchor.kind == "heading")
    heading_matches = {
        anchor.anchor_id: _matching_blocks(
            anchor,
            visible_blocks,
            allow_ocr_layout=allow_ocr_layout,
            enforce_kind=True,
        )
        for anchor in heading_anchors
    }
    table_anchors = tuple(anchor for anchor in policy.gold.anchors if anchor.kind in {"table_header", "table_row"})
    table_matches = {
        anchor.anchor_id: _matching_blocks(
            anchor,
            visible_blocks,
            allow_ocr_layout=allow_ocr_layout,
            enforce_kind=True,
        )
        for anchor in table_anchors
    }

    parse_status = _parse_status_dimension(parse_result)
    semantic_anchors = _ratio_dimension(
        "semantic_anchors",
        matched=sum(bool(matches) for matches in anchor_matches.values()),
        expected=len(policy.gold.anchors),
        failure_reason="semantic_anchor_missing",
    )
    heading_structure = _ratio_dimension(
        "heading_structure",
        matched=sum(bool(matches) for matches in heading_matches.values()),
        expected=len(heading_anchors),
        failure_reason="heading_structure_missing",
    )
    critical_tables = _ratio_dimension(
        "critical_tables",
        matched=sum(bool(matches) for matches in table_matches.values()),
        expected=len(table_anchors),
        failure_reason="critical_table_anchor_missing",
    )

    generic_locator_matches = {
        anchor.anchor_id: tuple(
            block for block in anchor_matches[anchor.anchor_id] if _has_required_locator(block, variant=variant)
        )
        for anchor in policy.gold.anchors
    }
    case_locator_matches = {
        (case.case_id, anchor_id): tuple(
            block
            for block in anchor_matches[anchor_id]
            if _has_required_locator(
                block,
                variant=variant,
                allowed_pdf_pages=(case.locator_constraints.pdf_pages if case.locator_constraints is not None else ()),
            )
        )
        for case in policy.gold.cases
        if not case.no_answer
        for anchor_id in case.evidence_anchor_ids
    }
    locator_matches: dict[str, tuple[ParsedBlock, ...]] = {}
    for anchor in policy.gold.anchors:
        case_matches = [
            matches for (case_id, anchor_id), matches in case_locator_matches.items() if anchor_id == anchor.anchor_id
        ]
        locator_matches[anchor.anchor_id] = (
            tuple(block for matches in case_matches for block in matches)
            if case_matches and all(case_matches)
            else (() if case_matches else generic_locator_matches[anchor.anchor_id])
        )
    provenance_locators = _ratio_dimension(
        "provenance_locators",
        matched=sum(bool(matches) for matches in locator_matches.values()),
        expected=len(policy.gold.anchors),
        failure_reason="provenance_locator_missing",
    )
    pdf_page_coverage = _pdf_page_dimension(variant=variant, blocks=visible_blocks)
    ocr_diagnostics = _ocr_dimension(
        variant=variant,
        blocks=visible_blocks,
        semantic_anchor_matches=sum(bool(matches) for matches in anchor_matches.values()),
    )
    warning_failures = _warning_failure_dimension(parse_result)

    observations = _build_observations(
        policy=policy,
        variant=variant,
        anchor_matches=anchor_matches,
        locator_matches=locator_matches,
        case_locator_matches=case_locator_matches,
    )
    case_results = _build_case_results(
        policy=policy,
        variant=variant,
        anchor_matches=anchor_matches,
        case_locator_matches=case_locator_matches,
    )
    safe_diagnostics = _safe_diagnostics(parse_result)
    outcome = _variant_outcome(
        variant=variant,
        parse_result=parse_result,
        dimensions=(
            parse_status,
            semantic_anchors,
            heading_structure,
            critical_tables,
            provenance_locators,
            pdf_page_coverage,
            ocr_diagnostics,
            warning_failures,
        ),
    )
    ocr_metadata = _first_ocr_metadata(visible_blocks)
    return ParserVariantResultV1(
        policy_id=policy.doc_key,
        variant=variant.format,
        source_type=_safe_code(parse_result.source_type, default=variant.source_type),
        parser_name=_safe_code(parse_result.parser_name, default="unknown_parser"),
        parser_version=_safe_code(parse_result.parser_version, default="unknown"),
        ocr_engine=_optional_safe_code(ocr_metadata.get("engine")),
        ocr_engine_version=_optional_safe_code(ocr_metadata.get("engine_version")),
        ocr_language=_optional_safe_code(ocr_metadata.get("language")),
        outcome=outcome,
        parse_status=parse_status,
        semantic_anchors=semantic_anchors,
        heading_structure=heading_structure,
        critical_tables=critical_tables,
        provenance_locators=provenance_locators,
        pdf_page_coverage=pdf_page_coverage,
        ocr_diagnostics=ocr_diagnostics,
        warning_failures=warning_failures,
        observations=observations,
        case_results=case_results,
        safe_diagnostics=safe_diagnostics,
    )


def _parse_one_fixture(
    *,
    registry: ParserRegistry,
    policy: FormatParityPolicy,
    variant: FormatParityVariant,
) -> ParseResult:
    path = (_REPOSITORY_ROOT / variant.path).resolve()
    metadata = _parser_metadata(policy=policy, variant=variant)
    try:
        parse_result = registry.parse(
            path,
            doc_key=policy.doc_key,
            source_type=variant.source_type,
            metadata=metadata,
        )
        if not isinstance(parse_result, ParseResult):
            raise TypeError("invalid parser result")
    except Exception:
        return safe_failed_result(
            source_type=variant.source_type,
            parser_name="moca_parser_registry",
            parser_version="21.01",
            failure_code="parser_invariant_error",
            safe_message="Parser registry call failed safely.",
            warnings=(
                ParserWarning(
                    code="parser_exception_sanitized",
                    message="Parser exception details were not retained.",
                ),
            ),
        )
    return replace(
        parse_result,
        blocks=tuple(block for block in parse_result.blocks if block.text.strip()),
    )


def _parser_metadata(
    *,
    policy: FormatParityPolicy,
    variant: FormatParityVariant,
) -> dict[str, Any]:
    declared_mime = "text/markdown" if variant.format == "markdown" else "application/pdf"
    return {
        "doc_key": policy.doc_key,
        "title": policy.title,
        "source_type": variant.source_type,
        "format": variant.format,
        "source_checksum": f"sha256:{variant.sha256}",
        "sha256": variant.sha256,
        "pages": variant.pages,
        "extractable_text_chars": variant.extractable_text_chars,
        "declared_mime": declared_mime,
    }


def _build_case_results(
    *,
    policy: FormatParityPolicy,
    variant: FormatParityVariant,
    anchor_matches: Mapping[str, tuple[ParsedBlock, ...]],
    case_locator_matches: Mapping[tuple[str, str], tuple[ParsedBlock, ...]],
) -> tuple[ParserCaseResultV1, ...]:
    results: list[ParserCaseResultV1] = []
    for case in sorted(policy.gold.cases, key=lambda item: item.case_id):
        expected = len(case.evidence_anchor_ids)
        if case.no_answer:
            results.append(
                ParserCaseResultV1(
                    policy_id=policy.doc_key,
                    variant=variant.format,
                    case_id=case.case_id,
                    category=case.category,
                    status="not_applicable",
                    matched_anchors=0,
                    expected_anchors=0,
                )
            )
            continue
        matched = sum(bool(anchor_matches[anchor_id]) for anchor_id in case.evidence_anchor_ids)
        locator_misses = [
            anchor_id for anchor_id in case.evidence_anchor_ids if not case_locator_matches[(case.case_id, anchor_id)]
        ]
        reasons: list[str] = []
        primary_stage: ParserPrimaryStage | None = None
        if matched != expected:
            reasons.append("semantic_anchor_missing")
            primary_stage = "ocr" if variant.format == "scanned_pdf" else "parser"
        elif locator_misses:
            reasons.append("provenance_locator_missing")
            primary_stage = "provenance"
        status: CaseStatus = "passed" if not reasons else "failed"
        results.append(
            ParserCaseResultV1(
                policy_id=policy.doc_key,
                variant=variant.format,
                case_id=case.case_id,
                category=case.category,
                status=status,
                matched_anchors=matched,
                expected_anchors=expected,
                anchor_recall=round(matched / expected, 6) if expected else None,
                primary_stage=primary_stage,
                reason_codes=tuple(reasons),
            )
        )
    return tuple(results)


def _comparison_copy(text: str, *, allow_ocr_layout: bool) -> str:
    copied = unicodedata.normalize("NFC", str(text)).replace("\u00a0", " ").replace("\u3000", " ")
    copied = _TABLE_LAYOUT.sub(" ", copied)
    copied = _WHITESPACE.sub(" ", copied).strip()
    if allow_ocr_layout:
        copied = _CJK_LAYOUT_WHITESPACE.sub("", copied)
    return copied


def _matching_blocks(
    anchor: SemanticAnchor,
    blocks: Sequence[ParsedBlock],
    *,
    allow_ocr_layout: bool,
    enforce_kind: bool,
) -> tuple[ParsedBlock, ...]:
    expected_types: set[str] | None = None
    if enforce_kind and anchor.kind == "heading":
        expected_types = {"heading", "header"}
    elif enforce_kind and anchor.kind in {"table_header", "table_row"}:
        expected_types = {"table"}

    matches: list[ParsedBlock] = []
    for block in blocks:
        if expected_types is not None and block.block_type not in expected_types:
            continue
        candidate = _block_comparison_text(block)
        if comparison_text_contains(anchor.text, candidate, allow_ocr_layout=allow_ocr_layout):
            matches.append(block)
    return tuple(matches)


def _block_comparison_text(block: ParsedBlock) -> str:
    pieces = [str(block.text), str(block.normalized_text)]
    if block.block_type == "table":
        pieces.extend(_table_comparison_fragments(block.table_metadata))
    return "\n".join(piece for piece in pieces if piece)


def _table_comparison_fragments(metadata: Mapping[str, Any]) -> tuple[str, ...]:
    fragments: list[str] = []
    headers = metadata.get("headers")
    if isinstance(headers, Sequence) and not isinstance(headers, str | bytes | bytearray):
        fragments.append(" ".join(str(item) for item in headers))
    rows = metadata.get("rows")
    if isinstance(rows, Sequence) and not isinstance(rows, str | bytes | bytearray):
        for row in rows:
            cells = row.get("cells") if isinstance(row, Mapping) else row
            if isinstance(cells, Sequence) and not isinstance(cells, str | bytes | bytearray):
                fragments.append(" ".join(str(item) for item in cells))
    return tuple(fragments)


def _has_required_locator(
    block: ParsedBlock,
    *,
    variant: FormatParityVariant,
    allowed_pdf_pages: tuple[int, ...] = (),
) -> bool:
    if not block.source_block_id:
        return False
    if variant.format == "markdown":
        return True
    return (
        block.page_number is not None
        and block.page_number > 0
        and block.box is not None
        and (not allowed_pdf_pages or block.page_number in allowed_pdf_pages)
    )


def _parse_status_dimension(parse_result: ParseResult) -> ParserDimensionV1:
    if parse_result.status == "success":
        return _dimension("parse_status", "passed", matched=1, expected=1)
    reason = "parse_status_degraded" if parse_result.status == "degraded" else "parse_status_failed"
    if parse_result.failure_code:
        reason = f"failure:{_safe_code(parse_result.failure_code, default='parser_failed')}"
    return _dimension("parse_status", "failed", matched=0, expected=1, reason_codes=(reason,))


def _ratio_dimension(
    dimension: DimensionName,
    *,
    matched: int,
    expected: int,
    failure_reason: str,
) -> ParserDimensionV1:
    if expected == 0:
        return _dimension(dimension, "not_applicable", matched=0, expected=0)
    status: DimensionStatus = "passed" if matched == expected else "failed"
    reasons = () if status == "passed" else (failure_reason,)
    return _dimension(dimension, status, matched=matched, expected=expected, reason_codes=reasons)


def _pdf_page_dimension(
    *,
    variant: FormatParityVariant,
    blocks: Sequence[ParsedBlock],
) -> ParserDimensionV1:
    if variant.format == "markdown" or variant.pages is None:
        return _dimension("pdf_page_coverage", "not_applicable", matched=0, expected=0)
    expected_pages = set(range(1, variant.pages + 1))
    actual_pages = {block.page_number for block in blocks if block.page_number in expected_pages}
    matched = len(actual_pages)
    return _ratio_dimension(
        "pdf_page_coverage",
        matched=matched,
        expected=len(expected_pages),
        failure_reason="pdf_page_missing",
    )


def _ocr_dimension(
    *,
    variant: FormatParityVariant,
    blocks: Sequence[ParsedBlock],
    semantic_anchor_matches: int,
) -> ParserDimensionV1:
    if variant.format != "scanned_pdf":
        return _dimension("ocr_diagnostics", "not_applicable", matched=0, expected=0)
    ocr_blocks = tuple(block for block in blocks if block.ocr_metadata or block.block_type == "ocr_text")
    reasons: list[str] = []
    if not ocr_blocks:
        reasons.append("ocr_output_empty")
    if semantic_anchor_matches == 0:
        reasons.append("ocr_anchor_recall_zero")
    if any(bool(block.ocr_metadata.get("timeout")) for block in ocr_blocks):
        reasons.append("ocr_timeout")
    if any(
        block.ocr_metadata.get("confidence_status") in {"rejected", "review_needed", "review_required"}
        for block in ocr_blocks
    ):
        reasons.append("ocr_output_garbled")
    if reasons:
        return _dimension(
            "ocr_diagnostics",
            "failed",
            matched=0,
            expected=1,
            reason_codes=tuple(sorted(set(reasons))),
        )
    return _dimension("ocr_diagnostics", "passed", matched=1, expected=1)


def _warning_failure_dimension(parse_result: ParseResult) -> ParserDimensionV1:
    reasons: list[str] = []
    if parse_result.status == "degraded":
        reasons.append("parse_status_degraded")
    if parse_result.status == "failed":
        reasons.append(f"failure:{_safe_code(parse_result.failure_code, default='parser_failed')}")
    reasons.extend(f"warning:{_safe_code(warning.code, default='parser_warning')}" for warning in parse_result.warnings)
    if reasons:
        return _dimension(
            "warning_failures",
            "failed",
            matched=0,
            expected=1,
            reason_codes=tuple(sorted(set(reasons))),
        )
    return _dimension("warning_failures", "passed", matched=1, expected=1)


def _dimension(
    dimension: DimensionName,
    status: DimensionStatus,
    *,
    matched: int,
    expected: int,
    reason_codes: tuple[str, ...] = (),
) -> ParserDimensionV1:
    recall = None if expected == 0 else round(matched / expected, 6)
    return ParserDimensionV1(
        dimension=dimension,
        status=status,
        matched=matched,
        expected=expected,
        recall=recall,
        reason_codes=tuple(sorted(reason_codes)),
    )


def _build_observations(
    *,
    policy: FormatParityPolicy,
    variant: FormatParityVariant,
    anchor_matches: Mapping[str, tuple[ParsedBlock, ...]],
    locator_matches: Mapping[str, tuple[ParsedBlock, ...]],
    case_locator_matches: Mapping[tuple[str, str], tuple[ParsedBlock, ...]],
) -> tuple[ParserObservationV1, ...]:
    case_ids_by_anchor: dict[str, list[str]] = {anchor.anchor_id: [] for anchor in policy.gold.anchors}
    for case in policy.gold.cases:
        for anchor_id in case.evidence_anchor_ids:
            case_ids_by_anchor[anchor_id].append(case.case_id)

    observations: list[ParserObservationV1] = []
    for anchor in policy.gold.anchors:
        case_ids = tuple(sorted(case_ids_by_anchor[anchor.anchor_id])) or ("_policy_anchor_inventory",)
        text_matched = bool(anchor_matches[anchor.anchor_id])
        for case_id in case_ids:
            locator_matched = bool(
                locator_matches[anchor.anchor_id]
                if case_id == "_policy_anchor_inventory"
                else case_locator_matches[(case_id, anchor.anchor_id)]
            )
            observations.append(
                ParserObservationV1(
                    policy_id=policy.doc_key,
                    variant=variant.format,
                    case_id=case_id,
                    anchor_id=anchor.anchor_id,
                    anchor_kind=anchor.kind,
                    expected_locator_summary=_expected_locator_summary(
                        policy=policy,
                        variant=variant,
                        case_id=case_id,
                    ),
                    status="matched" if text_matched else "missed",
                    primary_stage="ocr" if variant.format == "scanned_pdf" and not text_matched else "parser",
                    reason_code="anchor_matched" if text_matched else "semantic_anchor_missing",
                )
            )
            if text_matched and not locator_matched:
                observations.append(
                    ParserObservationV1(
                        policy_id=policy.doc_key,
                        variant=variant.format,
                        case_id=case_id,
                        anchor_id=anchor.anchor_id,
                        anchor_kind=anchor.kind,
                        expected_locator_summary=_expected_locator_summary(
                            policy=policy,
                            variant=variant,
                            case_id=case_id,
                        ),
                        status="missed",
                        primary_stage="provenance",
                        reason_code="provenance_locator_missing",
                    )
                )
    return tuple(
        sorted(
            observations,
            key=lambda item: (
                item.policy_id,
                _VARIANT_ORDER[item.variant],
                item.case_id,
                item.anchor_id,
                item.reason_code,
            ),
        )
    )


def _expected_locator_summary(
    *,
    policy: FormatParityPolicy,
    variant: FormatParityVariant,
    case_id: str,
) -> str:
    if variant.format == "markdown":
        return "source_block_id_required"
    pages: tuple[int, ...] = ()
    for case in policy.gold.cases:
        if case.case_id == case_id and case.locator_constraints is not None:
            pages = case.locator_constraints.pdf_pages
            break
    page_summary = ",".join(str(page) for page in sorted(pages)) if pages else "any"
    return f"pages={page_summary};page_and_box_required=true"


def _safe_diagnostics(parse_result: ParseResult) -> tuple[SafeParserDiagnosticV1, ...]:
    diagnostics: list[SafeParserDiagnosticV1] = []
    if parse_result.failure_code or parse_result.safe_message:
        diagnostics.append(
            SafeParserDiagnosticV1(
                code=_safe_code(parse_result.failure_code, default="parser_failed"),
                safe_snippet=_safe_snippet(parse_result.safe_message),
            )
        )
    diagnostics.extend(_warning_diagnostic(warning) for warning in parse_result.warnings)
    return tuple(
        sorted(
            diagnostics,
            key=lambda item: (
                item.block_index if item.block_index is not None else -1,
                item.code,
                item.safe_snippet or "",
            ),
        )
    )


def _warning_diagnostic(warning: ParserWarning) -> SafeParserDiagnosticV1:
    return SafeParserDiagnosticV1(
        code=_safe_code(warning.code, default="parser_warning"),
        block_index=warning.block_index,
        safe_snippet=_safe_snippet(warning.message),
    )


def _safe_snippet(value: Any) -> str | None:
    if value is None:
        return None
    text = unicodedata.normalize("NFC", str(value)).strip()
    if not text:
        return None
    if _CONTROL_CHARS.search(text) or _LOCAL_PATH.search(text) or _UNSAFE_DIAGNOSTIC.search(text):
        return "Parser diagnostic redacted."
    return _WHITESPACE.sub(" ", text)[:SAFE_SNIPPET_MAX_CHARS]


def _safe_code(value: Any, *, default: str) -> str:
    text = str(value or default).strip().lower()
    return text if _SAFE_CODE.fullmatch(text) else default


def _optional_safe_code(value: Any) -> str | None:
    if value is None:
        return None
    return _safe_code(value, default="unknown")


def _first_ocr_metadata(blocks: Iterable[ParsedBlock]) -> Mapping[str, Any]:
    for block in blocks:
        if block.ocr_metadata:
            return block.ocr_metadata
    return {}


def _variant_outcome(
    *,
    variant: FormatParityVariant,
    parse_result: ParseResult,
    dimensions: Sequence[ParserDimensionV1],
) -> EvaluationOutcome:
    failure_code = _safe_code(parse_result.failure_code, default="") if parse_result.failure_code else ""
    if failure_code in _OCR_UNAVAILABLE_CODES:
        return EvaluationOutcome.UNAVAILABLE_PREREQUISITE
    if variant.format == "scanned_pdf" and failure_code == "malformed_source" and not parse_result.blocks:
        return EvaluationOutcome.COMPLETED_QUALITY_FAIL
    if parse_result.status == "failed":
        return EvaluationOutcome.EXECUTION_ERROR
    if any(dimension.status == "failed" for dimension in dimensions):
        return EvaluationOutcome.COMPLETED_QUALITY_FAIL
    return EvaluationOutcome.COMPLETED_PASS


def _detect_ocr_prerequisite() -> ParserPrerequisiteV1:
    executable = shutil.which("tesseract")
    if executable is None:
        return ParserPrerequisiteV1(
            name="ocr_runtime",
            status="unavailable",
            reason_code="ocr_executable_unavailable",
            required_languages=("chi_sim", "eng"),
        )
    try:
        version_result = subprocess.run(  # noqa: S603
            [executable, "--version"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
        language_result = subprocess.run(  # noqa: S603
            [executable, "--list-langs"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return ParserPrerequisiteV1(
            name="ocr_runtime",
            status="unavailable",
            reason_code="ocr_runtime_unavailable",
            required_languages=("chi_sim", "eng"),
        )
    languages = {
        line.strip()
        for line in language_result.stdout.splitlines()
        if line.strip() and not line.lower().startswith("list of available languages")
    }
    if language_result.returncode != 0 or not {"chi_sim", "eng"}.issubset(languages):
        return ParserPrerequisiteV1(
            name="ocr_runtime",
            status="unavailable",
            reason_code="ocr_traineddata_unavailable",
            required_languages=("chi_sim", "eng"),
        )
    version_line = version_result.stdout.splitlines()[0] if version_result.stdout.splitlines() else "unknown"
    version_parts = version_line.split(maxsplit=1)
    version = _safe_code(version_parts[-1], default="unknown")
    return ParserPrerequisiteV1(
        name="ocr_runtime",
        status="available",
        reason_code="ocr_runtime_available",
        version=version,
        required_languages=("chi_sim", "eng"),
    )


def _with_unavailable_ocr(
    result: ParserVariantResultV1,
    *,
    reason_code: str,
) -> ParserVariantResultV1:
    return result.model_copy(
        update={
            "outcome": EvaluationOutcome.UNAVAILABLE_PREREQUISITE,
            "ocr_diagnostics": _dimension(
                "ocr_diagnostics",
                "failed",
                matched=0,
                expected=1,
                reason_codes=(reason_code,),
            ),
        }
    )


def _run_outcome(results: Sequence[ParserVariantResultV1]) -> EvaluationOutcome:
    outcomes = {result.outcome for result in results}
    for outcome in (
        EvaluationOutcome.EXECUTION_ERROR,
        EvaluationOutcome.UNAVAILABLE_PREREQUISITE,
        EvaluationOutcome.COMPLETED_QUALITY_FAIL,
        EvaluationOutcome.COMPLETED_PASS,
    ):
        if outcome in outcomes:
            return outcome
    return EvaluationOutcome.EXECUTION_ERROR


def _runtime_versions(
    results: Sequence[ParserVariantResultV1],
    *,
    ocr_prerequisite: ParserPrerequisiteV1,
) -> tuple[ParserRuntimeVersionV1, ...]:
    versions = {
        ParserRuntimeVersionV1(
            kind="parser",
            name=result.parser_name,
            version=result.parser_version,
        )
        for result in results
    }
    for result in results:
        if result.ocr_engine is not None:
            versions.add(
                ParserRuntimeVersionV1(
                    kind="ocr",
                    name=result.ocr_engine,
                    version=result.ocr_engine_version or ocr_prerequisite.version or "unknown",
                    language=result.ocr_language,
                )
            )
    if not any(item.kind == "ocr" for item in versions):
        versions.add(
            ParserRuntimeVersionV1(
                kind="ocr",
                name="tesseract",
                version=ocr_prerequisite.version or "unavailable",
                language="chi_sim+eng",
            )
        )
    return tuple(sorted(versions, key=lambda item: (item.kind, item.name, item.version, item.language or "")))


def _run_failures(results: Sequence[ParserVariantResultV1]) -> tuple[ParserRunFailureV1, ...]:
    failures: list[ParserRunFailureV1] = []
    for result in results:
        for dimension in (
            result.parse_status,
            result.semantic_anchors,
            result.heading_structure,
            result.critical_tables,
            result.provenance_locators,
            result.pdf_page_coverage,
            result.ocr_diagnostics,
            result.warning_failures,
        ):
            if dimension.status != "failed":
                continue
            primary_stage: ParserPrimaryStage = "parser"
            if dimension.dimension in {"provenance_locators", "pdf_page_coverage"}:
                primary_stage = "provenance"
            elif (
                result.variant == "scanned_pdf"
                and result.outcome == EvaluationOutcome.COMPLETED_QUALITY_FAIL
                and dimension.dimension
                in {
                    "parse_status",
                    "semantic_anchors",
                    "heading_structure",
                    "critical_tables",
                    "ocr_diagnostics",
                    "warning_failures",
                }
            ):
                primary_stage = "ocr"
            for reason_code in dimension.reason_codes or (f"{dimension.dimension}_failed",):
                failures.append(
                    ParserRunFailureV1(
                        policy_id=result.policy_id,
                        variant=result.variant,
                        primary_stage=primary_stage,
                        reason_code=reason_code,
                    )
                )
    return tuple(
        sorted(
            failures,
            key=lambda item: (
                item.policy_id,
                _VARIANT_ORDER[item.variant],
                item.primary_stage,
                item.reason_code,
            ),
        )
    )
