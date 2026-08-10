"""Fail-closed contracts for the RAG format-parity evaluation corpus."""

from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from pathlib import Path, PurePosixPath
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator


FORMAT_PARITY_DOC_KEYS = (
    "eval_refund_eligibility_and_return",
    "eval_quality_compensation_and_approval",
    "eval_cross_border_and_digital_goods",
)
FORMAT_VARIANTS = (
    ("markdown", "policy_markdown"),
    ("digital_pdf", "policy_pdf"),
    ("scanned_pdf", "policy_pdf"),
)
FORMAT_PARITY_CATEGORIES = frozenset(
    {
        "facts",
        "exceptions",
        "amounts_time_limits",
        "tables",
        "cross_section",
        "no_answer",
    }
)
_FIXTURE_ROOT = PurePosixPath("evaluation/rag_sources/fixtures")
_SHA256_PATTERN = r"^[0-9a-f]{64}$"
_FORBIDDEN_GOLD_KEYS = frozenset({"expected_chunk_id", "expected_chunk_ids"})


class EvaluationOutcome(StrEnum):
    """Shared execution vocabulary consumed by all parity evaluators."""

    COMPLETED_PASS = "completed_pass"
    COMPLETED_QUALITY_FAIL = "completed_quality_fail"
    UNAVAILABLE_PREREQUISITE = "unavailable_prerequisite"
    EXECUTION_ERROR = "execution_error"


class FormatParityContractError(ValueError):
    """Bounded, stable preflight failure without source bytes or absolute paths."""

    def __init__(self, reason_code: str, identifier: str = "format_parity_contract") -> None:
        self.reason_code = reason_code
        self.identifier = identifier
        super().__init__(f"{reason_code}: {identifier}")


class GeneratorIdentity(BaseModel):
    """Inputs whose exact identity owns generated fixture reuse."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["rag_format_parity_fixture_generator.v1"]
    builder_sha256: str = Field(pattern=_SHA256_PATTERN)
    profile: str = Field(min_length=1, max_length=128)
    reportlab_version: str = Field(min_length=1, max_length=64)
    pillow_version: str = Field(min_length=1, max_length=64)
    pypdfium2_version: str = Field(min_length=1, max_length=64)
    pdfplumber_version: str = Field(min_length=1, max_length=64)
    cjk_font_sha256: str = Field(pattern=_SHA256_PATTERN)
    raster_dpi: int = Field(gt=0, le=1200)
    deterministic_metadata_profile: str = Field(min_length=1, max_length=128)


class FormatParityVariant(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    format: Literal["markdown", "digital_pdf", "scanned_pdf"]
    path: str = Field(min_length=1, max_length=512)
    source_type: Literal["policy_markdown", "policy_pdf"]
    sha256: str = Field(pattern=_SHA256_PATTERN)
    pages: int | None
    extractable_text_chars: int = Field(ge=0)


class FormatParityManifestRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    parity_group: str = Field(min_length=1, max_length=128)
    doc_key: str = Field(min_length=1, max_length=128)
    title: str = Field(min_length=1, max_length=256)
    source_of_truth: str = Field(min_length=1, max_length=512)
    variants: tuple[FormatParityVariant, ...] = Field(min_length=3, max_length=3)
    generator_identity: GeneratorIdentity
    generator_identity_hash: str = Field(pattern=_SHA256_PATTERN)


class SemanticAnchor(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    anchor_id: str = Field(min_length=1, max_length=128)
    kind: Literal["heading", "fact", "table_header", "table_row"]
    section: str = Field(min_length=1, max_length=256)
    text: str = Field(min_length=1, max_length=1000)


class LocatorConstraints(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    pdf_pages: tuple[int, ...] = Field(default=(), max_length=5)
    ocr_whitespace_normalization: bool = False


class SemanticCase(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    case_id: str = Field(min_length=1, max_length=128)
    category: Literal[
        "facts",
        "exceptions",
        "amounts_time_limits",
        "tables",
        "cross_section",
        "no_answer",
    ]
    question: str = Field(min_length=1, max_length=1000)
    expected_section: str | None = Field(default=None, max_length=256)
    evidence_anchor_ids: tuple[str, ...] = Field(default=(), max_length=12)
    expected_answer: str | None = Field(default=None, max_length=2000)
    no_answer: bool
    locator_constraints: LocatorConstraints | None = None

    @model_validator(mode="after")
    def validate_no_answer_contract(self) -> SemanticCase:
        if self.no_answer:
            if self.category != "no_answer" or self.expected_answer is not None or self.evidence_anchor_ids:
                raise ValueError("no-answer cases cannot bind positive truth")
        elif (
            self.category == "no_answer"
            or not self.expected_answer
            or not self.expected_section
            or not self.evidence_anchor_ids
        ):
            raise ValueError("answerable cases require shared semantic truth")
        return self


class SemanticGoldPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    policy_id: str = Field(min_length=1, max_length=128)
    title: str = Field(min_length=1, max_length=256)
    anchors: tuple[SemanticAnchor, ...] = Field(min_length=8, max_length=12)
    cases: tuple[SemanticCase, ...] = Field(min_length=6, max_length=8)


class SemanticGoldEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["rag_format_parity_gold.v1"]
    policies: tuple[SemanticGoldPolicy, ...] = Field(min_length=3, max_length=3)


class FormatParityPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    doc_key: str
    title: str
    source_of_truth: str
    variants: tuple[FormatParityVariant, ...]
    gold: SemanticGoldPolicy
    generator_identity: GeneratorIdentity


class FormatParityDataset(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    manifest_hash: str = Field(pattern=_SHA256_PATTERN)
    gold_hash: str = Field(pattern=_SHA256_PATTERN)
    fixture_hashes: dict[str, str]
    policies: tuple[FormatParityPolicy, ...]
    baseline_identity: str = Field(pattern=_SHA256_PATTERN)


def load_format_parity_contract(
    manifest_path: Path,
    gold_path: Path,
    *,
    repository_root: Path,
) -> FormatParityDataset:
    """Validate the complete fixed corpus before returning evaluator input."""

    root = _validated_repository_root(repository_root)
    manifest_bytes = _read_contract_bytes(manifest_path, "manifest_file_invalid")
    manifest_records = _parse_manifest(manifest_bytes)
    records_by_key = _validate_manifest_groups(manifest_records)
    generator_identity_hash = _validate_generator_identity(records_by_key)
    fixture_hashes = _validate_fixture_records(records_by_key, repository_root=root)

    gold_bytes = _read_contract_bytes(gold_path, "gold_file_invalid")
    gold = _parse_gold(gold_bytes)
    gold_by_key = _validate_gold(gold)

    policies = tuple(
        FormatParityPolicy(
            doc_key=doc_key,
            title=records_by_key[doc_key].title,
            source_of_truth=records_by_key[doc_key].source_of_truth,
            variants=records_by_key[doc_key].variants,
            gold=gold_by_key[doc_key],
            generator_identity=records_by_key[doc_key].generator_identity,
        )
        for doc_key in FORMAT_PARITY_DOC_KEYS
    )
    manifest_hash = _sha256_bytes(manifest_bytes)
    gold_hash = _sha256_bytes(gold_bytes)
    baseline_identity = _baseline_identity(
        manifest_hash=manifest_hash,
        gold_hash=gold_hash,
        fixture_hashes=fixture_hashes,
        generator_identity_hash=generator_identity_hash,
    )
    return FormatParityDataset(
        manifest_hash=manifest_hash,
        gold_hash=gold_hash,
        fixture_hashes=fixture_hashes,
        policies=policies,
        baseline_identity=baseline_identity,
    )


def _validated_repository_root(repository_root: Path) -> Path:
    try:
        root = repository_root.resolve(strict=True)
    except (OSError, RuntimeError):
        raise FormatParityContractError("repository_root_invalid") from None
    if not root.is_dir():
        raise FormatParityContractError("repository_root_invalid")
    return root


def _read_contract_bytes(path: Path, reason_code: str) -> bytes:
    try:
        if not path.is_file():
            raise OSError
        return path.read_bytes()
    except OSError:
        raise FormatParityContractError(reason_code) from None


def _parse_manifest(payload: bytes) -> tuple[FormatParityManifestRecord, ...]:
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError:
        raise FormatParityContractError("manifest_encoding_invalid") from None
    records: list[FormatParityManifestRecord] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            raw = json.loads(line)
            records.append(FormatParityManifestRecord.model_validate(raw))
        except (json.JSONDecodeError, ValidationError):
            raise FormatParityContractError("manifest_schema_invalid", f"line_{line_number}") from None
    return tuple(records)


def _validate_manifest_groups(
    records: tuple[FormatParityManifestRecord, ...],
) -> dict[str, FormatParityManifestRecord]:
    records_by_key: dict[str, FormatParityManifestRecord] = {}
    for record in records:
        if record.doc_key in records_by_key:
            raise FormatParityContractError("duplicate_manifest_group", record.doc_key)
        records_by_key[record.doc_key] = record
    if len(records) != 3 or set(records_by_key) != set(FORMAT_PARITY_DOC_KEYS):
        raise FormatParityContractError("manifest_group_set_invalid")
    return records_by_key


def _validate_generator_identity(records_by_key: dict[str, FormatParityManifestRecord]) -> str:
    recorded_hashes: set[str] = set()
    identities: set[str] = set()
    for doc_key in FORMAT_PARITY_DOC_KEYS:
        record = records_by_key[doc_key]
        serialized = json.dumps(
            record.generator_identity.model_dump(mode="json"),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        actual_hash = _sha256_bytes(serialized.encode("utf-8"))
        if record.generator_identity_hash != actual_hash:
            raise FormatParityContractError("generator_identity_hash_mismatch", doc_key)
        recorded_hashes.add(record.generator_identity_hash)
        identities.add(serialized)
    if len(recorded_hashes) != 1 or len(identities) != 1:
        raise FormatParityContractError("generator_identity_mismatch")
    return next(iter(recorded_hashes))


def _validate_fixture_records(
    records_by_key: dict[str, FormatParityManifestRecord],
    *,
    repository_root: Path,
) -> dict[str, str]:
    fixture_hashes: dict[str, str] = {}
    for doc_key in FORMAT_PARITY_DOC_KEYS:
        record = records_by_key[doc_key]
        if record.parity_group != record.doc_key:
            raise FormatParityContractError("parity_group_mismatch", doc_key)
        variant_pairs = [(variant.format, variant.source_type) for variant in record.variants]
        if len(set(variant_pairs)) != 3 or set(variant_pairs) != set(FORMAT_VARIANTS):
            raise FormatParityContractError("manifest_variant_set_invalid", doc_key)
        variants_by_format = {variant.format: variant for variant in record.variants}
        markdown = variants_by_format["markdown"]
        if record.source_of_truth != markdown.path:
            raise FormatParityContractError("source_of_truth_mismatch", doc_key)

        directory = doc_key.removeprefix("eval_")
        base = f"evaluation/rag_sources/fixtures/{directory}/{directory}"
        expected_paths = {
            "markdown": f"{base}.md",
            "digital_pdf": f"{base}.digital.pdf",
            "scanned_pdf": f"{base}.scanned.pdf",
        }

        for variant_name, _ in FORMAT_VARIANTS:
            variant = variants_by_format[variant_name]
            if variant.path != expected_paths[variant_name]:
                raise FormatParityContractError("fixture_path_invalid", f"{doc_key}:{variant_name}")
            _validate_variant_metadata(variant, doc_key=doc_key)
            resolved_path = _resolve_fixture_path(variant.path, repository_root=repository_root, doc_key=doc_key)
            actual_hash = _sha256_file(resolved_path)
            if actual_hash != variant.sha256:
                raise FormatParityContractError("fixture_checksum_mismatch", f"{doc_key}:{variant.format}")
            fixture_hashes[variant.path] = actual_hash
    return fixture_hashes


def _validate_variant_metadata(variant: FormatParityVariant, *, doc_key: str) -> None:
    if variant.format == "markdown":
        valid = variant.pages is None and variant.extractable_text_chars > 0
    elif variant.format == "digital_pdf":
        valid = variant.pages is not None and variant.pages > 0 and variant.extractable_text_chars > 0
    else:
        valid = variant.pages is not None and variant.pages > 0 and variant.extractable_text_chars == 0
    if not valid:
        raise FormatParityContractError("variant_metadata_invalid", f"{doc_key}:{variant.format}")


def _resolve_fixture_path(path_text: str, *, repository_root: Path, doc_key: str) -> Path:
    pure_path = PurePosixPath(path_text)
    if (
        not path_text
        or "\\" in path_text
        or pure_path.is_absolute()
        or ".." in pure_path.parts
        or not pure_path.is_relative_to(_FIXTURE_ROOT)
    ):
        raise FormatParityContractError("fixture_path_invalid", doc_key)

    fixture_root = (repository_root / _FIXTURE_ROOT).resolve()
    try:
        resolved = (repository_root / pure_path).resolve(strict=True)
        resolved.relative_to(fixture_root)
    except (OSError, RuntimeError, ValueError):
        raise FormatParityContractError("fixture_path_invalid", doc_key) from None
    if not resolved.is_file():
        raise FormatParityContractError("fixture_path_invalid", doc_key)
    return resolved


def _parse_gold(payload: bytes) -> SemanticGoldEnvelope:
    try:
        raw: Any = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise FormatParityContractError("gold_schema_invalid") from None
    if _contains_forbidden_gold_key(raw):
        raise FormatParityContractError("gold_chunk_binding_forbidden")
    try:
        return SemanticGoldEnvelope.model_validate(raw)
    except ValidationError:
        raise FormatParityContractError("gold_schema_invalid") from None


def _contains_forbidden_gold_key(value: Any) -> bool:
    if isinstance(value, dict):
        return any(key in _FORBIDDEN_GOLD_KEYS or _contains_forbidden_gold_key(item) for key, item in value.items())
    if isinstance(value, list):
        return any(_contains_forbidden_gold_key(item) for item in value)
    return False


def _validate_gold(gold: SemanticGoldEnvelope) -> dict[str, SemanticGoldPolicy]:
    policies_by_key: dict[str, SemanticGoldPolicy] = {}
    case_ids: set[str] = set()
    anchor_ids: set[str] = set()
    categories: set[str] = set()
    for policy in gold.policies:
        if policy.policy_id in policies_by_key:
            raise FormatParityContractError("duplicate_gold_policy", policy.policy_id)
        policies_by_key[policy.policy_id] = policy
        local_anchor_ids = {anchor.anchor_id for anchor in policy.anchors}
        if len(local_anchor_ids) != len(policy.anchors) or anchor_ids.intersection(local_anchor_ids):
            raise FormatParityContractError("gold_anchor_id_invalid", policy.policy_id)
        anchor_ids.update(local_anchor_ids)
        for case in policy.cases:
            if case.case_id in case_ids:
                raise FormatParityContractError("gold_case_id_invalid", case.case_id)
            case_ids.add(case.case_id)
            categories.add(case.category)
            if not set(case.evidence_anchor_ids).issubset(local_anchor_ids):
                raise FormatParityContractError("gold_anchor_reference_invalid", case.case_id)
    if set(policies_by_key) != set(FORMAT_PARITY_DOC_KEYS):
        raise FormatParityContractError("gold_policy_set_invalid")
    if categories != FORMAT_PARITY_CATEGORIES:
        raise FormatParityContractError("gold_category_set_invalid")
    return policies_by_key


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
    except OSError:
        raise FormatParityContractError("fixture_file_invalid") from None
    return digest.hexdigest()


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _baseline_identity(
    *,
    manifest_hash: str,
    gold_hash: str,
    fixture_hashes: dict[str, str],
    generator_identity_hash: str,
) -> str:
    payload = json.dumps(
        {
            "schema_version": "rag_format_parity_baseline_inputs.v1",
            "manifest_hash": manifest_hash,
            "gold_hash": gold_hash,
            "fixture_hashes": fixture_hashes,
            "generator_identity_hash": generator_identity_hash,
        },
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return _sha256_bytes(payload)
