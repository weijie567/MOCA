"""Exact same-run character/token A-B selection and immutable evidence.

All decision arithmetic is integer, :class:`fractions.Fraction`, or
:class:`decimal.Decimal`. Six-place formatting exists only in the Markdown
projection and never feeds a gate.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from fractions import Fraction
import hashlib
import json
import os
from pathlib import Path
import tempfile
from typing import Any, Callable, Literal, Mapping, TypeVar
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from src.rag.embedding_tokenizer import ProviderParityStatus
from src.rag.evaluation.reporting import canonical_report_json_bytes, validate_safe_report_payload
from src.rag.policy_reindex import PolicyReindexRunIdentity
from src.rag.provider_execution_authority import (
    ProviderExecutionPurpose,
    ProviderExecutionReservationRequestV1,
    ProviderExecutionReservationViewV1,
    ProviderExecutionResultCode,
    ProviderExecutionResultRequestV1,
    ProviderExecutionResultViewV1,
    ProviderRequestEnvelopeV1,
    ProjectionReconciliationViewV1,
    canonical_sha256,
)
from src.rag.policy_reindex_artifacts import (
    PolicyReindexArtifactError,
    load_policy_reindex_recovery_descriptor,
    load_policy_reindex_state,
    policy_reindex_descriptor_path,
)
from src.rag.tokenizer_parity import TokenizerParityError, load_parity_report


RUN_SCHEMA_VERSION = "rag_token_chunk_ab.v1"
SELECTION_SCHEMA_VERSION = "rag_token_chunk_selection.v1"
EXECUTION_DIAGNOSTIC_SCHEMA_VERSION = "rag_token_chunk_execution_diagnostic.v1"
EXECUTION_BUNDLE_SCHEMA_VERSION = "rag_token_chunk_execution_bundle.v1"
RECOVERY_BUDGET_SCHEMA_VERSION = "rag_token_chunk_recovery_budget.v1"
RECOVERY_ATTEMPT_SCHEMA_VERSION = "rag_token_chunk_recovery_attempt.v1"
RECOVERY_AUTHORIZATION_SCHEMA_VERSION = "rag_token_chunk_recovery_authorization.v1"
DB_ACTIVATION_AUTHORIZATION_SCHEMA_VERSION = "rag_token_chunk_db_activation_authorization.v1"
GATE_PROFILE_VERSION = "rag_token_chunk_ab.v1"
SEALED_MANIFEST_HASH = "e5544b20ecdf05c2eaf3325b4e5f89a4ef752c0b8c0d23b8bac224f006fdd53b"
SEALED_GOLD_HASH = "c6dc12536270fa9b9532ec4595e0a91d2b4ebddf83754a0f1ec107caabb64b8e"
SEALED_DATASET_BASELINE_IDENTITY = "3b1ddd8c19f8fce0a37ad113f3d1161039c200e39e60ce0f2e4d0917d870e110"
SEALED_ANSWERABLE_CASE_COUNT = 45
SEALED_TOTAL_CASE_COUNT = 54
_SHA256_PATTERN = r"^sha256:[0-9a-f]{64}$"
_DIGEST_PATTERN = r"^[0-9a-f]{64}$"
_FORMAT_ORDER = ("markdown", "digital_pdf", "scanned_pdf")
_FRESH_PARITY_MAXIMUM_AGE = timedelta(hours=24)
PLAN12_RECOVERY_BUDGET_ID = "phase64.4-plan12-live-selection-recovery"
PLAN10_BASELINE_PROOF_SHA256 = "sha256:4dae8f0ec1c9e4c7b2010786fbd94f05af7b2d8623f0ae4df196d14ff26823f3"
PLAN10_FORBIDDEN_SELECTION_ID = UUID("30ffe6e0-6f91-4429-91b2-2dee8c20ee73")
_PLAN12_MAX_ATTEMPTS = 2
_PLAN12_MAX_EMBEDDING_TOKENS = 512
_PLAN12_TARGET_EMBEDDING_TOKENS = 384
_PLAN12_OVERLAP_TOKENS = 48
_CANONICAL_RECOVERY_RELATIVE_ROOT = Path("evaluation/reports/rag_token_chunk_ab/v1")
_TRANSIENT_EXECUTION_RETRY = ("retrieval_resource_proof", "provider_request_failed")
_UNAVAILABLE_RETRY_REASONS = {
    "provider_credentials_unavailable",
    "provider_request_unavailable",
    "provider_usage_unavailable",
}
_ProviderT = TypeVar("_ProviderT")
CANONICAL_AB_PROVIDER_BATCH_SIZE = 10
CANONICAL_AB_SDK_RETRIES = 0
CANONICAL_AB_OUTER_ATTEMPTS = 1
CANONICAL_AB_REWRITE_REQUEST_COUNT_PER_ROLE_FORMAT = 3
CANONICAL_AB_QUERY_REQUEST_COUNT = 126


class _FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class RecoveryAttemptRefused(ValueError):
    """A fail-closed refusal raised before provider construction or invocation."""


def canonical_recovery_root(*, repository_root: Path) -> Path:
    """Return the sole repository-owned production A-B authority root."""

    try:
        resolved_repository = repository_root.resolve(strict=True)
    except OSError:
        raise RecoveryAttemptRefused("repository_root_invalid") from None
    if not resolved_repository.is_dir():
        raise RecoveryAttemptRefused("repository_root_invalid")
    return (resolved_repository / _CANONICAL_RECOVERY_RELATIVE_ROOT).resolve(strict=False)


def require_canonical_recovery_root(*, output_root: Path, repository_root: Path) -> Path:
    """Reject alternate, copied, outside, or symlinked production roots."""

    try:
        resolved_repository = repository_root.resolve(strict=True)
    except OSError:
        raise RecoveryAttemptRefused("repository_root_invalid") from None
    expected_lexical = resolved_repository / _CANONICAL_RECOVERY_RELATIVE_ROOT
    selected_lexical = output_root if output_root.is_absolute() else resolved_repository / output_root
    selected_lexical = Path(os.path.abspath(selected_lexical))
    if selected_lexical != expected_lexical:
        raise RecoveryAttemptRefused("recovery_root_not_canonical")
    try:
        relative = selected_lexical.relative_to(resolved_repository)
        current = resolved_repository
        for part in relative.parts:
            current = current / part
            if current.exists() and current.is_symlink():
                raise RecoveryAttemptRefused("recovery_root_not_canonical")
        resolved = selected_lexical.resolve(strict=False)
    except (OSError, ValueError):
        raise RecoveryAttemptRefused("recovery_root_not_canonical") from None
    if resolved != canonical_recovery_root(repository_root=resolved_repository):
        raise RecoveryAttemptRefused("recovery_root_not_canonical")
    return resolved


class ExactRatioV1(_FrozenModel):
    numerator: int = Field(ge=0)
    denominator: int = Field(gt=0)

    @property
    def fraction(self) -> Fraction:
        return Fraction(self.numerator, self.denominator)

    @classmethod
    def from_fraction(cls, value: Fraction) -> ExactRatioV1:
        if value < 0:
            raise ValueError("negative_ratio")
        return cls(numerator=value.numerator, denominator=value.denominator)


class ABFormatMetricsV1(_FrozenModel):
    format: Literal["markdown", "digital_pdf", "scanned_pdf"]
    hit_at_1: ExactRatioV1
    hit_at_3: ExactRatioV1
    hit_at_5: ExactRatioV1
    mrr: ExactRatioV1

    @model_validator(mode="after")
    def validate_rates(self) -> ABFormatMetricsV1:
        if any(value.fraction > 1 for value in (self.hit_at_1, self.hit_at_3, self.hit_at_5, self.mrr)):
            raise ValueError("format_metric_out_of_range")
        return self


class ABQualityMetricsV1(_FrozenModel):
    answerable_case_count: Literal[45]
    total_case_count: Literal[54]
    hit_at_1: ExactRatioV1
    hit_at_3: ExactRatioV1
    hit_at_5: ExactRatioV1
    mrr: ExactRatioV1
    semantic_anchor_coverage: ExactRatioV1
    locator_coverage: ExactRatioV1
    fallback_correctness: ExactRatioV1
    by_format: tuple[ABFormatMetricsV1, ...] = Field(min_length=3, max_length=3)

    @model_validator(mode="after")
    def validate_quality(self) -> ABQualityMetricsV1:
        ratios = (
            self.hit_at_1,
            self.hit_at_3,
            self.hit_at_5,
            self.mrr,
            self.semantic_anchor_coverage,
            self.locator_coverage,
            self.fallback_correctness,
        )
        if any(value.fraction > 1 for value in ratios):
            raise ValueError("quality_metric_out_of_range")
        if tuple(item.format for item in self.by_format) != _FORMAT_ORDER:
            raise ValueError("format_metric_order_mismatch")
        return self

    @property
    def hit_at_5_spread(self) -> ExactRatioV1:
        values = [item.hit_at_5.fraction for item in self.by_format]
        return ExactRatioV1.from_fraction(max(values) - min(values))


class ABEmbeddingCostV1(_FrozenModel):
    basis_version: str = Field(min_length=1, max_length=128)
    currency: Literal["CNY", "USD"]
    unit_tokens: int = Field(gt=0)
    price_per_unit: Decimal = Field(ge=0)
    estimated_cost: Decimal = Field(ge=0)
    observed_cost: Decimal | None = Field(default=None, ge=0)
    observed_cost_status: Literal["provider_reported", "unavailable"]

    @model_validator(mode="after")
    def validate_observed_cost(self) -> ABEmbeddingCostV1:
        if (self.observed_cost is None) != (self.observed_cost_status == "unavailable"):
            raise ValueError("observed_cost_status_mismatch")
        return self


class ABResourceMetricsV1(_FrozenModel):
    chunk_count: int = Field(gt=0)
    duplicate_count: int = Field(ge=0)
    offline_embedding_tokens: int = Field(gt=0)
    provider_embedding_tokens: int | None = Field(default=None, ge=0)
    provider_tokens_status: Literal["provider_reported", "unavailable"]
    retrieval_duration_ms: Decimal = Field(ge=0)
    embedding_cost: ABEmbeddingCostV1

    @model_validator(mode="after")
    def validate_resources(self) -> ABResourceMetricsV1:
        if self.duplicate_count > self.chunk_count:
            raise ValueError("duplicate_count_invalid")
        if (self.provider_embedding_tokens is None) != (self.provider_tokens_status == "unavailable"):
            raise ValueError("provider_token_status_mismatch")
        expected_cost = (
            Decimal(self.offline_embedding_tokens)
            * self.embedding_cost.price_per_unit
            / Decimal(self.embedding_cost.unit_tokens)
        )
        if self.embedding_cost.estimated_cost != expected_cost:
            raise ValueError("estimated_cost_mismatch")
        return self

    @property
    def duplicate_rate(self) -> ExactRatioV1:
        return ExactRatioV1(numerator=self.duplicate_count, denominator=self.chunk_count)


class ABCandidateObservationV1(_FrozenModel):
    role: Literal["incumbent", "candidate"]
    assembler: Literal["CharacterCompatibilityAssembler", "PolicyEmbeddingInputAssembler"]
    config_schema_version: str = Field(min_length=1, max_length=128)
    config_fingerprint: str = Field(pattern=_SHA256_PATTERN)
    corpus_version_id: UUID
    deterministic_rebuild_sha256: str = Field(pattern=_SHA256_PATTERN)
    quality: ABQualityMetricsV1
    resources: ABResourceMetricsV1

    @model_validator(mode="after")
    def validate_role_assembler(self) -> ABCandidateObservationV1:
        expected = "CharacterCompatibilityAssembler" if self.role == "incumbent" else "PolicyEmbeddingInputAssembler"
        if self.assembler != expected:
            raise ValueError("candidate_assembler_mismatch")
        return self


class ABInputIdentityV1(_FrozenModel):
    manifest_hash: Literal["e5544b20ecdf05c2eaf3325b4e5f89a4ef752c0b8c0d23b8bac224f006fdd53b"] = SEALED_MANIFEST_HASH
    gold_hash: Literal["c6dc12536270fa9b9532ec4595e0a91d2b4ebddf83754a0f1ec107caabb64b8e"] = SEALED_GOLD_HASH
    dataset_baseline_identity: Literal["3b1ddd8c19f8fce0a37ad113f3d1161039c200e39e60ce0f2e4d0917d870e110"] = (
        SEALED_DATASET_BASELINE_IDENTITY
    )
    baseline_report_sha256: str = Field(pattern=_SHA256_PATTERN)
    ordered_questions_sha256: str = Field(pattern=_SHA256_PATTERN)
    answerable_case_count: Literal[45] = SEALED_ANSWERABLE_CASE_COUNT
    total_case_count: Literal[54] = SEALED_TOTAL_CASE_COUNT


class CanonicalABIngestionInputV1(_FrozenModel):
    role: Literal["incumbent", "candidate"]
    round_format: Literal["markdown", "digital_pdf", "scanned_pdf"]
    doc_key: str = Field(min_length=1, max_length=128)
    source_sha256: str = Field(pattern=_SHA256_PATTERN)
    assembler_fingerprint: str = Field(pattern=_SHA256_PATTERN)
    parser_status: Literal["success", "degraded", "failed"]
    parser_failure_code: str | None = Field(default=None, max_length=128)
    exact_assembled_input_count: int = Field(ge=0)
    ordered_input_hashes: tuple[str, ...]
    ordered_batch_call_sites: tuple[str, ...]

    @model_validator(mode="after")
    def validate_ingestion_batches(self) -> CanonicalABIngestionInputV1:
        expected_batches = (
            self.exact_assembled_input_count + CANONICAL_AB_PROVIDER_BATCH_SIZE - 1
        ) // CANONICAL_AB_PROVIDER_BATCH_SIZE
        if (
            len(self.ordered_input_hashes) != self.exact_assembled_input_count
            or any(not _valid_sha256(value) for value in self.ordered_input_hashes)
            or len(self.ordered_batch_call_sites) != expected_batches
            or len(set(self.ordered_batch_call_sites)) != len(self.ordered_batch_call_sites)
            or (self.parser_status == "failed") != (self.parser_failure_code is not None)
        ):
            raise ValueError("canonical_ab_ingestion_envelope_invalid")
        return self


class CanonicalABRequestEnvelopeV1(_FrozenModel):
    """Offline-computed, source-bound maximum for one complete canonical A/B."""

    schema_version: Literal["canonical_ab_request_envelope.v1"] = "canonical_ab_request_envelope.v1"
    provider_batch_size: Literal[10] = CANONICAL_AB_PROVIDER_BATCH_SIZE
    sdk_retries: Literal[0] = CANONICAL_AB_SDK_RETRIES
    maximum_outer_attempts: Literal[1] = CANONICAL_AB_OUTER_ATTEMPTS
    base_question_count: Literal[18]
    rewrite_request_count_per_role_format: Literal[3] = CANONICAL_AB_REWRITE_REQUEST_COUNT_PER_ROLE_FORMAT
    query_request_count: Literal[126] = CANONICAL_AB_QUERY_REQUEST_COUNT
    ingestion_request_count: int = Field(ge=0)
    ordered_ingestion_inputs: tuple[CanonicalABIngestionInputV1, ...] = Field(min_length=18, max_length=18)
    ordered_query_call_sites: tuple[str, ...] = Field(min_length=126, max_length=126)
    provider_request_envelope: ProviderRequestEnvelopeV1
    canonical_hash: str = Field(pattern=_SHA256_PATTERN)

    @classmethod
    def seal(cls, **values: Any) -> CanonicalABRequestEnvelopeV1:
        payload = {"schema_version": "canonical_ab_request_envelope.v1", **values}
        canonical_payload = cls.model_construct(
            **payload,
            canonical_hash="sha256:" + "0" * 64,
        ).model_dump(mode="json", exclude={"canonical_hash"})
        return cls(**canonical_payload, canonical_hash=_sha256_payload(canonical_payload))

    @model_validator(mode="after")
    def validate_complete_call_graph(self) -> CanonicalABRequestEnvelopeV1:
        ingestion_sites = tuple(
            site for item in self.ordered_ingestion_inputs for site in item.ordered_batch_call_sites
        )
        provider = self.provider_request_envelope
        if (
            (self.base_question_count + self.rewrite_request_count_per_role_format) * len(_FORMAT_ORDER) * 2
            != self.query_request_count
            or len(self.ordered_query_call_sites) != self.query_request_count
            or len(ingestion_sites) != self.ingestion_request_count
            or provider.maximum_request_count != self.query_request_count + self.ingestion_request_count
            or set(provider.ordered_call_sites) != set((*ingestion_sites, *self.ordered_query_call_sites))
            or len(provider.ordered_call_sites) != len(set(provider.ordered_call_sites))
            or provider.maximum_attempts_per_site != (CANONICAL_AB_OUTER_ATTEMPTS,) * len(provider.ordered_call_sites)
            or _sha256_payload(self.model_dump(mode="json", exclude={"canonical_hash"})) != self.canonical_hash
        ):
            raise ValueError("canonical_ab_request_envelope_invalid")
        return self


def build_canonical_ab_request_envelope(
    *,
    dataset: Any,
    incumbent_assembler: Any,
    candidate_assembler: Any,
    repository_root: Path | None = None,
) -> CanonicalABRequestEnvelopeV1:
    """Enumerate the real two-role ingestion/query call graph without provider work."""

    from src.knowledge.retrieval import QUERY_PREFIX
    from src.knowledge.rewrite import build_query_rewrite_plan
    from src.rag.evaluation.retrieval_rounds import build_knowledge_query, ordered_gold_questions
    from src.rag.ingestion import assemble_policy_embedding_inputs
    from src.rag.parsers.registry import ParserRegistry
    from src.repositories.rag_evaluation_round_repo import ROUND_FORMATS

    root = (repository_root or Path.cwd()).resolve(strict=True)
    questions = ordered_gold_questions(dataset)
    if len(questions) != 18 or tuple(ROUND_FORMATS) != _FORMAT_ORDER or len(dataset.policies) != 3:
        raise ValueError("canonical_ab_sealed_call_graph_mismatch")

    candidate_config = candidate_assembler.config
    incumbent_config = incumbent_assembler.counter.config
    runtime_identity = (
        str(candidate_config.provider),
        str(candidate_config.model),
        int(candidate_config.dimensions),
    )
    if (
        runtime_identity
        != (
            str(incumbent_config.provider),
            str(incumbent_config.model),
            int(incumbent_config.dimensions),
        )
        or int(candidate_config.provider_max_batch_inputs) != CANONICAL_AB_PROVIDER_BATCH_SIZE
    ):
        raise ValueError("canonical_ab_provider_config_mismatch")

    parser_registry = ParserRegistry()
    all_call_sites: list[str] = []
    ingestion_inputs: list[CanonicalABIngestionInputV1] = []
    query_call_sites: list[str] = []
    roles = (
        ("incumbent", incumbent_assembler, str(incumbent_assembler.config_fingerprint)),
        ("candidate", candidate_assembler, str(candidate_config.config_fingerprint)),
    )
    for role, assembler, assembler_fingerprint in roles:
        for round_format in ROUND_FORMATS:
            for policy in dataset.policies:
                variant = next((item for item in policy.variants if item.format == round_format), None)
                if variant is None:
                    raise ValueError("canonical_ab_variant_missing")
                source_path = Path(variant.path)
                if not source_path.is_absolute():
                    source_path = root / source_path
                try:
                    source_payload = source_path.read_bytes()
                except OSError:
                    raise ValueError("canonical_ab_source_unavailable") from None
                if hashlib.sha256(source_payload).hexdigest() != variant.sha256:
                    raise ValueError("canonical_ab_source_hash_mismatch")
                metadata = {
                    "doc_key": policy.doc_key,
                    "title": policy.title,
                    "doc_type": "evaluation_policy",
                    "risk_level": "low",
                    "source_type": variant.source_type,
                }
                parsed = parser_registry.parse(
                    source_path,
                    doc_key=policy.doc_key,
                    source_type=variant.source_type,
                    metadata=metadata,
                )
                blocks = tuple(block for block in parsed.blocks if block.text.strip())
                assembled = assemble_policy_embedding_inputs(
                    blocks=blocks,
                    doc_key=policy.doc_key,
                    title=policy.title,
                    doc_type="evaluation_policy",
                    risk_level="low",
                    input_assembler=assembler,
                )
                ordered_hashes = tuple(item.embedding_input_hash for item in assembled)
                batch_sites: list[str] = []
                for batch_index, offset in enumerate(range(0, len(ordered_hashes), CANONICAL_AB_PROVIDER_BATCH_SIZE)):
                    batch_hashes = ordered_hashes[offset : offset + CANONICAL_AB_PROVIDER_BATCH_SIZE]
                    batch_hash = _sha256_payload(
                        {
                            "schema_version": "canonical_ab_ingestion_batch.v1",
                            "role": role,
                            "round_format": round_format,
                            "doc_key": policy.doc_key,
                            "batch_index": batch_index,
                            "input_count": len(batch_hashes),
                            "ordered_input_hashes": batch_hashes,
                        }
                    )
                    site = (
                        f"ab/{role}/{round_format}/ingest/{policy.doc_key}/"
                        f"{batch_index}/{len(batch_hashes)}/{batch_hash}"
                    )
                    batch_sites.append(site)
                    all_call_sites.append(site)
                ingestion_inputs.append(
                    CanonicalABIngestionInputV1(
                        role=role,
                        round_format=round_format,
                        doc_key=policy.doc_key,
                        source_sha256="sha256:" + variant.sha256,
                        assembler_fingerprint=assembler_fingerprint,
                        parser_status=parsed.status,
                        parser_failure_code=parsed.failure_code,
                        exact_assembled_input_count=len(ordered_hashes),
                        ordered_input_hashes=ordered_hashes,
                        ordered_batch_call_sites=tuple(batch_sites),
                    )
                )
            for query_index, (doc_key, case_id, question) in enumerate(questions):
                _, context = build_knowledge_query(
                    question=question,
                    generated_at="1970-01-01T00:00:00Z",
                )
                rewrite_plan = build_query_rewrite_plan(question, context)
                provider_queries = (("original", 0, question),) + tuple(
                    ("rewrite", rewrite_index, rewritten)
                    for rewrite_index, rewritten in enumerate(rewrite_plan.rewritten_queries, start=1)
                )
                for query_kind, channel_index, provider_query in provider_queries:
                    input_hash = (
                        "sha256:" + hashlib.sha256(f"{QUERY_PREFIX}{provider_query}".encode("utf-8")).hexdigest()
                    )
                    site = (
                        f"ab/{role}/{round_format}/query/{query_index}/{query_kind}/"
                        f"{channel_index}/{doc_key}/{case_id}/1/{input_hash}"
                    )
                    query_call_sites.append(site)
                    all_call_sites.append(site)

    from src.rag.policy_reindex import PROVIDER_EXECUTION_ENVELOPE_CONTRACT_HASH

    provider_envelope = ProviderRequestEnvelopeV1.seal(
        schema_version="canonical_ab_provider_request_envelope.v1",
        contract_hash=PROVIDER_EXECUTION_ENVELOPE_CONTRACT_HASH,
        ordered_call_sites=tuple(all_call_sites),
        maximum_attempts_per_site=(CANONICAL_AB_OUTER_ATTEMPTS,) * len(all_call_sites),
        maximum_request_count=len(all_call_sites),
        provider_name=runtime_identity[0],
        model_name=runtime_identity[1],
        dimensions=runtime_identity[2],
    )
    return CanonicalABRequestEnvelopeV1.seal(
        provider_batch_size=CANONICAL_AB_PROVIDER_BATCH_SIZE,
        sdk_retries=CANONICAL_AB_SDK_RETRIES,
        maximum_outer_attempts=CANONICAL_AB_OUTER_ATTEMPTS,
        base_question_count=len(questions),
        rewrite_request_count_per_role_format=(
            len(query_call_sites) // (len(roles) * len(ROUND_FORMATS)) - len(questions)
        ),
        query_request_count=len(query_call_sites),
        ingestion_request_count=sum(len(item.ordered_batch_call_sites) for item in ingestion_inputs),
        ordered_ingestion_inputs=tuple(ingestion_inputs),
        ordered_query_call_sites=tuple(query_call_sites),
        provider_request_envelope=provider_envelope,
    )


class ABNamespaceV1(_FrozenModel):
    corpus_version_id: UUID
    round_owner: str = Field(min_length=1, max_length=128)


class ABRuntimeConfigV1(_FrozenModel):
    schema_version: Literal["rag_token_chunk_ab_runtime.v1"] = "rag_token_chunk_ab_runtime.v1"
    execution_kind: Literal["full_provider", "contract_test"]
    tenant_id: UUID
    owner_marker: Literal["moca.rag_token_chunk_ab.v1"]
    provider: Literal["dashscope"]
    embedding_model: Literal["text-embedding-v4"]
    embedding_dimensions: Literal[1024]
    provider_runtime_identity: str = Field(min_length=1, max_length=128)
    retrieval_config_version: str = Field(min_length=1, max_length=128)
    rrf_config: str = Field(min_length=1, max_length=256)
    rewrite_config: str = Field(min_length=1, max_length=256)
    reranker_config: str = Field(min_length=1, max_length=256)
    no_evidence_threshold: Decimal = Field(ge=0, le=1)
    incumbent: ABNamespaceV1
    candidate: ABNamespaceV1

    @model_validator(mode="after")
    def validate_isolation(self) -> ABRuntimeConfigV1:
        if (
            self.incumbent.corpus_version_id == self.candidate.corpus_version_id
            or self.incumbent.round_owner == self.candidate.round_owner
        ):
            raise ValueError("ab_namespace_not_isolated")
        return self


class ABParityEvidenceV1(_FrozenModel):
    report_sha256: str = Field(pattern=_SHA256_PATTERN)
    run_id: UUID
    captured_at: datetime
    status: Literal["passed", "quarantined", "unavailable"]
    config_fingerprint: str = Field(pattern=_SHA256_PATTERN)
    probe_fixture_sha256: str = Field(pattern=_SHA256_PATTERN)
    submitted_content_sha256: str = Field(pattern=_SHA256_PATTERN)
    reason_code: str = Field(min_length=1, max_length=128)

    @model_validator(mode="after")
    def validate_parity_status(self) -> ABParityEvidenceV1:
        if self.captured_at.tzinfo is None:
            raise ValueError("parity_capture_time_invalid")
        expected = {
            "passed": {"exact_match"},
            "quarantined": {"single_count_mismatch", "aggregate_count_mismatch"},
            "unavailable": {
                "provider_credentials_unavailable",
                "provider_request_unavailable",
                "provider_usage_unavailable",
            },
        }
        if self.reason_code not in expected[self.status]:
            raise ValueError("parity_reason_mismatch")
        return self


class ABHardProofsV1(_FrozenModel):
    zero_final_input_overflow: bool
    persisted_counts_recomputed: bool
    deterministic_rebuild: bool
    complete_source_coverage: bool
    immutable_identity_replay: bool
    interrupted_resume_safe: bool
    stale_cas_safe: bool
    atomic_cutover_rollback_safe: bool
    evaluation_cleanup_isolated: bool
    fresh_provider_parity_passed: bool

    @property
    def all_passed(self) -> bool:
        return all(self.model_dump().values())


GateName = Literal[
    "hit_at_5",
    "cross_format_hit_at_5_spread",
    "hit_at_1_non_regression",
    "hit_at_3_non_regression",
    "mrr_non_regression",
    "format_hit_at_5_markdown",
    "format_hit_at_5_digital_pdf",
    "format_hit_at_5_scanned_pdf",
    "semantic_anchor_non_regression",
    "locator_non_regression",
    "fallback_non_regression",
    "duplicate_rate",
    "chunk_count_ratio",
    "embedding_token_ratio",
]


class ABGateObservationV1(_FrozenModel):
    profile_version: Literal["rag_token_chunk_ab.v1"] = GATE_PROFILE_VERSION
    gate: GateName
    operator: Literal[">=", "<="]
    candidate: ExactRatioV1
    incumbent: ExactRatioV1 | None
    limit: ExactRatioV1
    passed: bool

    @model_validator(mode="after")
    def validate_decision(self) -> ABGateObservationV1:
        expected = (
            self.candidate.fraction >= self.limit.fraction
            if self.operator == ">="
            else self.candidate.fraction <= self.limit.fraction
        )
        if self.passed is not expected:
            raise ValueError("gate_decision_mismatch")
        return self


class TerminalABRunV1(_FrozenModel):
    schema_version: Literal["rag_token_chunk_ab.v1"] = RUN_SCHEMA_VERSION
    run_id: UUID
    generated_at: datetime
    outcome: Literal["selected_pass", "candidate_failed", "unavailable", "execution_error"]
    failure_class: Literal["quality_fail", "safety_fail"] | None
    terminal_stage: Literal["selection", "quality", "safety", "parity", "provider", "execution"]
    safe_reason_codes: tuple[str, ...] = ()
    inputs: ABInputIdentityV1
    runtime: ABRuntimeConfigV1
    parity: ABParityEvidenceV1
    incumbent: ABCandidateObservationV1 | None
    candidate: ABCandidateObservationV1 | None
    hard_proofs: ABHardProofsV1 | None
    gates: tuple[ABGateObservationV1, ...]

    @model_validator(mode="after")
    def validate_terminal_shape(self) -> TerminalABRunV1:
        if self.generated_at.tzinfo is None:
            raise ValueError("generated_at_invalid")
        completed = self.outcome in {"selected_pass", "candidate_failed"}
        if completed:
            if None in (self.incumbent, self.candidate, self.hard_proofs) or len(self.gates) != 14:
                raise ValueError("completed_observations_missing")
            assert self.incumbent is not None and self.candidate is not None and self.hard_proofs is not None
            if self.incumbent.role != "incumbent" or self.candidate.role != "candidate":
                raise ValueError("candidate_role_mismatch")
            if (
                self.incumbent.corpus_version_id != self.runtime.incumbent.corpus_version_id
                or self.candidate.corpus_version_id != self.runtime.candidate.corpus_version_id
                or self.candidate.config_fingerprint != self.parity.config_fingerprint
            ):
                raise ValueError("candidate_runtime_identity_mismatch")
            recomputed = evaluate_exact_gates(incumbent=self.incumbent, candidate=self.candidate)
            if self.gates != recomputed:
                raise ValueError("gate_observation_mismatch")
            age = self.generated_at.astimezone(UTC) - self.parity.captured_at.astimezone(UTC)
            parity_fresh = (
                self.parity.status == "passed"
                and timedelta(0) <= age <= _FRESH_PARITY_MAXIMUM_AGE
                and self.hard_proofs.fresh_provider_parity_passed
            )
            if not parity_fresh:
                raise ValueError("fresh_passed_parity_required")
            safety_failed = not self.hard_proofs.all_passed
            quality_failed = any(not gate.passed for gate in self.gates)
            if self.outcome == "selected_pass":
                if self.runtime.execution_kind != "full_provider":
                    raise ValueError("selected_pass_requires_full_provider")
                if safety_failed or quality_failed or self.failure_class is not None or self.safe_reason_codes:
                    raise ValueError("selected_pass_shape_invalid")
                if self.terminal_stage != "selection":
                    raise ValueError("selected_pass_stage_invalid")
            else:
                expected_class = "safety_fail" if safety_failed else "quality_fail"
                expected_stage = "safety" if safety_failed else "quality"
                expected_reason = "hard_safety_gate_failed" if safety_failed else "quality_gate_failed"
                if (
                    self.failure_class != expected_class
                    or self.terminal_stage != expected_stage
                    or self.safe_reason_codes != (expected_reason,)
                    or (not safety_failed and not quality_failed)
                ):
                    raise ValueError("candidate_failed_shape_invalid")
        else:
            if any(value is not None for value in (self.incumbent, self.candidate, self.hard_proofs)) or self.gates:
                raise ValueError("non_completed_quality_evidence")
            if self.failure_class is not None or not self.safe_reason_codes:
                raise ValueError("non_completed_reason_missing")
            expected_stages = {"unavailable": {"parity", "provider"}, "execution_error": {"execution"}}
            if self.terminal_stage not in expected_stages[self.outcome]:
                raise ValueError("non_completed_stage_invalid")
        validate_safe_report_payload(self.model_dump(mode="json"))
        return self


def canonical_ab_result_code(report: TerminalABRunV1) -> ProviderExecutionResultCode:
    """Map one truthful terminal A/B outcome to the committed DB result class."""

    if report.outcome == "selected_pass":
        return ProviderExecutionResultCode.SUCCESS
    if report.outcome == "candidate_failed":
        return (
            ProviderExecutionResultCode.SAFETY_FAIL
            if report.failure_class == "safety_fail"
            else ProviderExecutionResultCode.QUALITY_FAIL
        )
    if report.outcome == "unavailable":
        return ProviderExecutionResultCode.PROVIDER_UNAVAILABLE
    return ProviderExecutionResultCode.UNKNOWN_ERROR


@dataclass(frozen=True, slots=True)
class CanonicalABExecutionOutcomeV1:
    report: TerminalABRunV1
    binding: ABSelectionBindingV1 | None
    reservation: ProviderExecutionReservationViewV1
    result: ProviderExecutionResultViewV1
    projection: ProjectionReconciliationViewV1


def canonical_ab_subject_hash(
    *,
    expected_run_id: UUID,
    owner: PolicyReindexRunIdentity,
    inputs: ABInputIdentityV1,
    envelope: CanonicalABRequestEnvelopeV1,
) -> str:
    """Bind the A/B reservation to one exact shared-root comparison."""

    if not isinstance(expected_run_id, UUID) or expected_run_id.int == 0:
        raise ValueError("canonical_ab_run_id_invalid")
    return canonical_sha256(
        {
            "schema_version": "canonical_ab_subject.v2",
            "run_id": expected_run_id,
            "tenant_id": owner.tenant_id,
            "run_token": owner.run_token,
            "candidate_corpus_version_id": owner.corpus_version_id,
            "incumbent_corpus_version_id": owner.source_active_corpus_version_id,
            "candidate_state_version": owner.state_version,
            "candidate_config_fingerprint": owner.config_fingerprint,
            "candidate_parity_report_hash": owner.provider_parity_report_hash,
            "candidate_source_manifest_revision_id": owner.source_manifest_revision_id,
            "candidate_source_manifest_hash": owner.source_manifest_hash,
            "candidate_source_rollout_epoch": owner.source_rollout_epoch,
            "candidate_evidence_rollout_version": owner.expected_evidence_rollout_version,
            "candidate_lease_expires_at": owner.lease_expires_at,
            "inputs": inputs.model_dump(mode="json"),
            "request_envelope_hash": envelope.canonical_hash,
        }
    )


def require_exact_canonical_ab_lineage(
    *,
    expected_run_id: UUID,
    report: TerminalABRunV1,
    binding: ABSelectionBindingV1 | None,
    owner: PolicyReindexRunIdentity,
    reservation: ProviderExecutionReservationViewV1,
    request: ProviderExecutionReservationRequestV1,
) -> None:
    """Reject report/selection bytes not owned by the reserved DB subject."""

    from src.rag.evaluation.retrieval_rounds import build_ab_round_namespaces

    expected_namespaces = build_ab_round_namespaces(
        run_id=expected_run_id,
        incumbent_corpus_version_id=owner.source_active_corpus_version_id,
        candidate_corpus_version_id=owner.corpus_version_id,
    )
    report_lineage = (
        report.run_id,
        report.runtime.tenant_id,
        report.runtime.incumbent.corpus_version_id,
        report.runtime.candidate.corpus_version_id,
        report.runtime.provider,
        report.runtime.embedding_model,
        report.runtime.embedding_dimensions,
        report.runtime.incumbent.round_owner,
        report.runtime.candidate.round_owner,
    )
    expected_report_lineage = (
        expected_run_id,
        owner.tenant_id,
        owner.source_active_corpus_version_id,
        owner.corpus_version_id,
        request.request_envelope.provider_name,
        request.request_envelope.model_name,
        request.request_envelope.dimensions,
        expected_namespaces[0].round_owner,
        expected_namespaces[1].round_owner,
    )
    if report_lineage != expected_report_lineage:
        raise ValueError("canonical_ab_report_lineage_mismatch")

    try:
        reserved_request = ProviderExecutionReservationRequestV1.model_validate(
            reservation.model_dump(
                exclude={"schema_version", "reservation_id", "tenant_id", "predecessor_result_id", "reserved_at"}
            )
        )
    except ValueError:
        raise ValueError("canonical_ab_reservation_lineage_mismatch") from None
    if reservation.tenant_id != owner.tenant_id or reserved_request != request:
        raise ValueError("canonical_ab_reservation_lineage_mismatch")

    if report.outcome != "selected_pass":
        if binding is not None:
            raise ValueError("canonical_ab_selection_lineage_mismatch")
        return
    if report.candidate is None or binding is None:
        raise ValueError("canonical_ab_selection_lineage_mismatch")
    if (
        report.parity.report_sha256 != owner.provider_parity_report_hash
        or report.parity.config_fingerprint != owner.config_fingerprint
        or report.candidate.config_fingerprint != owner.config_fingerprint
        or (
            binding.tenant_id,
            binding.candidate_corpus_version_id,
            binding.candidate_run_token,
            binding.candidate_lease_owner,
            binding.source_manifest_hash,
        )
        != (
            owner.tenant_id,
            owner.corpus_version_id,
            owner.run_token,
            owner.lease_owner,
            owner.source_manifest_hash,
        )
    ):
        raise ValueError("canonical_ab_selection_lineage_mismatch")


def canonical_ab_typed_failure_result_code(
    *,
    stage: str,
    reason_code: str,
    provider_availability: str,
    provider_request_classification: str,
    outer_rollback_attempted: bool,
    outer_rollback_proved: bool,
    provider_request_count: int,
) -> ProviderExecutionResultCode:
    """Map validated typed provenance to the sole permitted DB result code."""

    explicitly_transient = (
        (stage, reason_code) == _TRANSIENT_EXECUTION_RETRY
        and provider_availability == "available"
        and provider_request_classification == "request_failed"
        and outer_rollback_attempted
        and outer_rollback_proved
        and provider_request_count > 0
    )
    if explicitly_transient:
        return ProviderExecutionResultCode.TRANSIENT_EXECUTION_ERROR
    if reason_code in {"candidate_state_invalid", "candidate_pair_invalid"}:
        return ProviderExecutionResultCode.SOURCE_DRIFT
    if reason_code in {"sealed_input_invalid", "role_setup_failed"}:
        return ProviderExecutionResultCode.CONFIGURATION_ERROR
    if reason_code == "provider_request_failed":
        return ProviderExecutionResultCode.RESPONSE_ERROR
    if reason_code in {"format_ingestion_failed", "resource_proof_failed", "rollback_proof_failed"}:
        return ProviderExecutionResultCode.PROJECTION_ERROR
    return ProviderExecutionResultCode.UNKNOWN_ERROR


@dataclass(frozen=True, slots=True)
class CanonicalABRunResultV1:
    """One typed execution result carried unchanged into terminal persistence."""

    report: TerminalABRunV1
    binding: ABSelectionBindingV1 | None
    diagnostic: ABExecutionDiagnosticV1 | None
    actual_request_count: int
    result_code: ProviderExecutionResultCode


class CanonicalABExecutionService:
    """Reserve and persist one canonical A/B beneath the shared DB root."""

    def __init__(self, *, authority_service: Any, require_shared_root: Callable[..., Any]) -> None:
        self._authority = authority_service
        self._require_shared_root = require_shared_root

    async def execute(
        self,
        *,
        authority_id: UUID,
        expected_run_id: UUID,
        owner: PolicyReindexRunIdentity,
        inputs: ABInputIdentityV1,
        envelope: CanonicalABRequestEnvelopeV1,
        ordinal: int,
        run: Callable[[Any], Any],
        projection_path: Path,
        persist_terminal: Callable[
            [
                CanonicalABRunResultV1,
                ProviderExecutionReservationViewV1,
                UUID,
            ],
            Mapping[str, Any],
        ],
        construct_provider: Callable[[], Any] | None = None,
    ) -> CanonicalABExecutionOutcomeV1:
        await self._authority.require_current_promotion()
        await self._require_shared_root(authority_id=authority_id, owner=owner, envelope=envelope)
        request = ProviderExecutionReservationRequestV1(
            authority_id=authority_id,
            purpose=ProviderExecutionPurpose.CANONICAL_AB,
            subject_kind="canonical_ab_run",
            subject_index=0,
            subject_hash=canonical_ab_subject_hash(
                expected_run_id=expected_run_id,
                owner=owner,
                inputs=inputs,
                envelope=envelope,
            ),
            ordinal=ordinal,
            request_envelope=envelope.provider_request_envelope,
            explicit_retry=ordinal == 2,
        )
        reservation = await self._authority.reserve_and_commit(request)
        await self._authority.recheck_dispatch(reservation)

        try:
            provider = construct_provider() if construct_provider is not None else None
            execution = await run(provider)
        except BaseException:
            # A committed reservation is deliberately spent; process crashes
            # cannot be converted into fabricated terminal evidence.
            raise
        if not isinstance(execution, CanonicalABRunResultV1):
            raise ValueError("canonical_ab_execution_result_invalid")
        report = execution.report
        binding = execution.binding
        diagnostic = execution.diagnostic
        actual_request_count = execution.actual_request_count
        result_code = execution.result_code
        if not isinstance(report, TerminalABRunV1):
            raise ValueError("canonical_ab_terminal_result_invalid")
        if report.inputs != inputs or report.runtime.tenant_id != owner.tenant_id:
            raise ValueError("canonical_ab_terminal_identity_mismatch")
        if (
            type(actual_request_count) is not int
            or not 0 <= actual_request_count <= envelope.provider_request_envelope.maximum_request_count
        ):
            raise ValueError("canonical_ab_request_count_invalid")
        if (
            report.runtime.execution_kind == "full_provider"
            and report.outcome in {"selected_pass", "candidate_failed"}
            and actual_request_count != envelope.provider_request_envelope.maximum_request_count
        ):
            raise ValueError("canonical_ab_complete_request_count_invalid")
        if report.outcome == "execution_error":
            expected_terminal_hash = canonical_sha256(canonical_report_json_bytes(report.model_dump(mode="json")))
            if (
                not isinstance(diagnostic, ABExecutionDiagnosticV1)
                or diagnostic.run_id != report.run_id
                or diagnostic.terminal_run_sha256 != expected_terminal_hash
                or report.safe_reason_codes != (diagnostic.reason_code,)
            ):
                raise ValueError("canonical_ab_execution_diagnostic_mismatch")
        elif diagnostic is not None:
            raise ValueError("canonical_ab_execution_diagnostic_forbidden")

        expected_result_code = canonical_ab_result_code(report)
        if report.outcome == "execution_error":
            assert diagnostic is not None
            expected_result_code = canonical_ab_typed_failure_result_code(
                stage=diagnostic.stage,
                reason_code=diagnostic.reason_code,
                provider_availability=diagnostic.provider_availability,
                provider_request_classification=diagnostic.provider_request_classification,
                outer_rollback_attempted=diagnostic.outer_rollback_attempted,
                outer_rollback_proved=diagnostic.outer_rollback_proved,
                provider_request_count=diagnostic.provider_request_count,
            )
        if result_code is not expected_result_code:
            raise ValueError("canonical_ab_result_code_invalid")

        require_exact_canonical_ab_lineage(
            expected_run_id=expected_run_id,
            report=report,
            binding=binding,
            owner=owner,
            reservation=reservation,
            request=request,
        )
        result_id = uuid4()
        persisted_lineage = persist_terminal(execution, reservation, result_id)
        terminal_run_hash = persisted_lineage.get("terminal_run_hash")
        terminal_report_hash = persisted_lineage.get("terminal_report_hash")
        if not isinstance(terminal_run_hash, str) or not isinstance(terminal_report_hash, str):
            raise ValueError("canonical_ab_terminal_lineage_missing")
        selected_lineage: Mapping[str, Any] = {}
        if report.outcome == "selected_pass":
            selected_lineage = persisted_lineage
            if any(
                not isinstance(selected_lineage.get(field), str)
                for field in ("selection_decision_hash", "activation_authorization_hash")
            ):
                raise ValueError("canonical_ab_selected_lineage_missing")
        elif any(
            persisted_lineage.get(field) is not None
            for field in ("selection_decision_hash", "activation_authorization_hash")
        ):
            raise ValueError("canonical_ab_nonselected_lineage_forbidden")

        result = await self._authority.record_result(
            ProviderExecutionResultRequestV1.seal(
                result_id=result_id,
                reservation_id=reservation.reservation_id,
                result_code=result_code,
                actual_request_count=actual_request_count,
                result_json={
                    "schema_version": "canonical_ab_db_result.v1",
                    "run_id": str(report.run_id),
                    "outcome": report.outcome,
                    "terminal_stage": report.terminal_stage,
                    "terminal_run_hash": terminal_run_hash,
                    "terminal_report_hash": terminal_report_hash,
                    "selection_decision_hash": selected_lineage.get("selection_decision_hash"),
                    "activation_authorization_hash": selected_lineage.get("activation_authorization_hash"),
                },
                output_candidate_id=owner.corpus_version_id if report.outcome == "selected_pass" else None,
                terminal_run_hash=terminal_run_hash,
                terminal_report_hash=terminal_report_hash,
                selection_id=binding.selection_id if binding is not None else None,
                selection_decision_hash=selected_lineage.get("selection_decision_hash"),
                activation_authorization_hash=selected_lineage.get("activation_authorization_hash"),
            )
        )
        projection = await self._authority.reconcile_projection(
            authority_id=authority_id,
            projection_path=projection_path,
        )
        return CanonicalABExecutionOutcomeV1(
            report=report,
            binding=binding,
            reservation=reservation,
            result=result,
            projection=projection,
        )


class ABSelectionBindingV1(_FrozenModel):
    selection_id: UUID
    tenant_id: UUID
    candidate_corpus_version_id: UUID
    candidate_run_token: UUID
    candidate_lease_owner: str = Field(min_length=1, max_length=128)
    source_manifest_hash: str = Field(pattern=_SHA256_PATTERN)


class ABSelectionDecisionV1(_FrozenModel):
    schema_version: Literal["rag_token_chunk_selection.v1"] = SELECTION_SCHEMA_VERSION
    selection_id: UUID
    selected_at: datetime
    outcome: Literal["selected_pass"] = "selected_pass"
    terminal_run_id: UUID
    terminal_run_sha256: str = Field(pattern=_SHA256_PATTERN)
    provider_parity_report_sha256: str = Field(pattern=_SHA256_PATTERN)
    tenant_id: UUID
    candidate_corpus_version_id: UUID
    candidate_run_token: UUID
    candidate_lease_owner: str = Field(min_length=1, max_length=128)
    source_manifest_hash: str = Field(pattern=_SHA256_PATTERN)
    manifest_hash: str = Field(pattern=_DIGEST_PATTERN)
    gold_hash: str = Field(pattern=_DIGEST_PATTERN)
    dataset_baseline_identity: str = Field(pattern=_DIGEST_PATTERN)
    runtime_config_sha256: str = Field(pattern=_SHA256_PATTERN)
    candidate_observation_sha256: str = Field(pattern=_SHA256_PATTERN)
    exact_gate_profile_sha256: str = Field(pattern=_SHA256_PATTERN)
    decision_payload_sha256: str = Field(pattern=_SHA256_PATTERN)

    @model_validator(mode="after")
    def validate_decision_hash(self) -> ABSelectionDecisionV1:
        if self.selected_at.tzinfo is None:
            raise ValueError("selection_time_invalid")
        expected = _sha256_payload(self.model_dump(mode="json", exclude={"decision_payload_sha256"}))
        if self.decision_payload_sha256 != expected:
            raise ValueError("selection_decision_hash_mismatch")
        validate_safe_report_payload(self.model_dump(mode="json"))
        return self


DiagnosticRole = Literal["character_incumbent", "token_candidate", "shared_preflight"]
DiagnosticRound = Literal["markdown", "digital_pdf", "scanned_pdf"]
DiagnosticStage = Literal[
    "shared_preflight",
    "role_setup",
    "format_ingestion",
    "retrieval_resource_proof",
    "post_rollback_baseline_verification",
]
DiagnosticReasonCode = Literal[
    "candidate_state_invalid",
    "sealed_input_invalid",
    "candidate_pair_invalid",
    "role_setup_failed",
    "format_ingestion_failed",
    "provider_request_failed",
    "resource_proof_failed",
    "rollback_proof_failed",
    "provider_execution_failed",
]


class ABExecutionDiagnosticV1(_FrozenModel):
    """Strict disclosure-safe provenance for one terminal execution error."""

    schema_version: Literal["rag_token_chunk_execution_diagnostic.v1"] = EXECUTION_DIAGNOSTIC_SCHEMA_VERSION
    run_id: UUID
    terminal_run_sha256: str = Field(pattern=_SHA256_PATTERN)
    occurred_at: datetime
    failing_role: DiagnosticRole
    round_format: DiagnosticRound | None = None
    stage: DiagnosticStage
    reason_code: DiagnosticReasonCode
    provider_availability: Literal["available", "unavailable", "not_checked"]
    provider_request_classification: Literal[
        "not_attempted",
        "request_started",
        "request_completed",
        "request_failed",
    ]
    outer_rollback_attempted: bool
    outer_rollback_proved: bool
    completed_round_count: int = Field(ge=0, le=3)
    provider_request_count: int = Field(ge=0)
    safe_context_sha256: str | None = Field(default=None, pattern=_SHA256_PATTERN)

    @model_validator(mode="after")
    def validate_diagnostic(self) -> ABExecutionDiagnosticV1:
        if self.occurred_at.tzinfo is None:
            raise ValueError("diagnostic_time_invalid")
        if self.outer_rollback_proved and not self.outer_rollback_attempted:
            raise ValueError("rollback_proof_invalid")
        if self.provider_request_classification in {"request_started", "request_completed"}:
            if self.provider_availability != "available":
                raise ValueError("provider_classification_invalid")
        if self.provider_request_classification == "not_attempted" and self.provider_request_count:
            raise ValueError("provider_request_count_invalid")
        validate_safe_report_payload(self.model_dump(mode="json"))
        return self


class ABExecutionBundleManifestV1(_FrozenModel):
    """The sole reader-visible commit point for an execution-error bundle."""

    schema_version: Literal["rag_token_chunk_execution_bundle.v1"] = EXECUTION_BUNDLE_SCHEMA_VERSION
    run_id: UUID
    terminal_run_sha256: str = Field(pattern=_SHA256_PATTERN)
    run_markdown_sha256: str = Field(pattern=_SHA256_PATTERN)
    diagnostic_json_sha256: str = Field(pattern=_SHA256_PATTERN)
    diagnostic_markdown_sha256: str = Field(pattern=_SHA256_PATTERN)

    @model_validator(mode="after")
    def validate_manifest(self) -> ABExecutionBundleManifestV1:
        validate_safe_report_payload(self.model_dump(mode="json"))
        return self


@dataclass(frozen=True, slots=True)
class ImmutableArtifactPairV1:
    json_path: Path
    markdown_path: Path
    json_sha256: str
    markdown_sha256: str


@dataclass(frozen=True, slots=True)
class ImmutableExecutionBundleV1:
    manifest: ABExecutionBundleManifestV1
    manifest_path: Path
    run: ImmutableArtifactPairV1
    diagnostic: ImmutableArtifactPairV1


@dataclass(frozen=True, slots=True)
class LoadedExecutionBundleV1:
    manifest: ABExecutionBundleManifestV1
    report: TerminalABRunV1
    diagnostic: ABExecutionDiagnosticV1


class RecoveryPriorRunV1(_FrozenModel):
    run_id: UUID
    terminal_run_sha256: str = Field(pattern=_SHA256_PATTERN)


PLAN10_TERMINAL_RUNS = (
    RecoveryPriorRunV1(
        run_id=UUID("3d4dae9c-a692-482d-b172-965edf5890e0"),
        terminal_run_sha256="sha256:ccf81982904b795c9dd15289c437dc32a4bd8a8cac1ba65bd9cba4011035843a",
    ),
    RecoveryPriorRunV1(
        run_id=UUID("1628accd-05ea-495e-8961-b74c18d6b85c"),
        terminal_run_sha256="sha256:196468c117cfb93d996d4c36bbe9aaa190e30258c29913d558ff26700a23a2e8",
    ),
    RecoveryPriorRunV1(
        run_id=UUID("9aa10545-2350-4053-b4ef-03a57fda0535"),
        terminal_run_sha256="sha256:863a88ec87c575668712e4b56937b45d7d24d9773f0af0dbe8e6b8b89e9d7c49",
    ),
)


class ABRecoveryBudgetManifestV1(_FrozenModel):
    """Fixed Plan12 authority; it cannot be widened after live observation."""

    schema_version: Literal["rag_token_chunk_recovery_budget.v1"] = RECOVERY_BUDGET_SCHEMA_VERSION
    budget_id: Literal["phase64.4-plan12-live-selection-recovery"] = PLAN12_RECOVERY_BUDGET_ID
    phase: Literal["64.4"] = "64.4"
    plan: Literal["12"] = "12"
    created_at: datetime
    max_attempts: Literal[2] = _PLAN12_MAX_ATTEMPTS
    plan10_terminal_runs: tuple[RecoveryPriorRunV1, RecoveryPriorRunV1, RecoveryPriorRunV1]
    plan10_baseline_proof_sha256: Literal["sha256:4dae8f0ec1c9e4c7b2010786fbd94f05af7b2d8623f0ae4df196d14ff26823f3"] = (
        PLAN10_BASELINE_PROOF_SHA256
    )
    tenant_id: UUID
    incumbent_corpus_version_id: UUID
    candidate_corpus_version_id: UUID
    candidate_run_token: UUID
    candidate_lease_owner: str = Field(min_length=1, max_length=128)
    candidate_state_version: int = Field(gt=0)
    candidate_state_relative_path: str = Field(min_length=1, max_length=512)
    candidate_state_sha256: str = Field(pattern=_SHA256_PATTERN)
    candidate_recovery_descriptor_sha256: str = Field(pattern=_SHA256_PATTERN)
    candidate_config_schema_version: str = Field(min_length=1, max_length=128)
    candidate_config_fingerprint: str = Field(pattern=_SHA256_PATTERN)
    candidate_source_manifest_revision_id: UUID
    candidate_source_manifest_revision: int = Field(gt=0)
    candidate_source_manifest_hash: str = Field(pattern=_SHA256_PATTERN)
    candidate_source_active_corpus_version_id: UUID
    candidate_source_rollout_epoch: int = Field(gt=0)
    candidate_expected_evidence_rollout_version: int = Field(ge=0)
    provider_parity_run_id: UUID
    provider_parity_report_sha256: str = Field(pattern=_SHA256_PATTERN)
    provider_parity_config_fingerprint: str = Field(pattern=_SHA256_PATTERN)
    provider_parity_probe_fixture_sha256: str = Field(pattern=_SHA256_PATTERN)
    provider_parity_submitted_content_sha256: str = Field(pattern=_SHA256_PATTERN)
    provider: Literal["dashscope"] = "dashscope"
    embedding_model: Literal["text-embedding-v4"] = "text-embedding-v4"
    embedding_dimensions: Literal[1024] = 1024
    max_embedding_tokens: Literal[512] = _PLAN12_MAX_EMBEDDING_TOKENS
    target_embedding_tokens: Literal[384] = _PLAN12_TARGET_EMBEDDING_TOKENS
    overlap_tokens: Literal[48] = _PLAN12_OVERLAP_TOKENS
    manifest_hash: Literal["e5544b20ecdf05c2eaf3325b4e5f89a4ef752c0b8c0d23b8bac224f006fdd53b"] = SEALED_MANIFEST_HASH
    gold_hash: Literal["c6dc12536270fa9b9532ec4595e0a91d2b4ebddf83754a0f1ec107caabb64b8e"] = SEALED_GOLD_HASH
    dataset_baseline_identity: Literal["3b1ddd8c19f8fce0a37ad113f3d1161039c200e39e60ce0f2e4d0917d870e110"] = (
        SEALED_DATASET_BASELINE_IDENTITY
    )
    manifest_payload_sha256: str = Field(pattern=_SHA256_PATTERN)

    @model_validator(mode="after")
    def validate_recovery_budget(self) -> ABRecoveryBudgetManifestV1:
        if self.created_at.tzinfo is None:
            raise ValueError("recovery_budget_time_invalid")
        if self.plan10_terminal_runs != PLAN10_TERMINAL_RUNS:
            raise ValueError("plan10_terminal_identity_mismatch")
        if self.incumbent_corpus_version_id == self.candidate_corpus_version_id:
            raise ValueError("recovery_candidate_not_isolated")
        expected_state_path = (
            Path("candidates")
            / "tenants"
            / str(self.tenant_id)
            / "runs"
            / str(self.candidate_run_token)
            / "states"
            / f"{self.candidate_state_version:08d}.json"
        ).as_posix()
        if self.candidate_state_relative_path != expected_state_path:
            raise ValueError("recovery_candidate_state_path_invalid")
        if self.provider_parity_config_fingerprint != self.candidate_config_fingerprint:
            raise ValueError("recovery_parity_candidate_mismatch")
        expected = _sha256_payload(self.model_dump(mode="json", exclude={"manifest_payload_sha256"}))
        if self.manifest_payload_sha256 != expected:
            raise ValueError("recovery_budget_hash_mismatch")
        validate_safe_report_payload(self.model_dump(mode="json"))
        return self


RecoveryAuthorityReason = Literal[
    "initial_attempt_allowed",
    "selected_pass_stops_budget",
    "candidate_failed_stops_budget",
    "transient_execution_error_retry_allowed",
    "rollback_unproved_stops_budget",
    "implementation_defect_stops_budget",
    "execution_evidence_invalid_stops_budget",
    "unavailable_prerequisite_change_retry_allowed",
    "prerequisite_state_unchanged_stops_budget",
    "unavailable_reason_not_allowlisted_stops_budget",
    "unavailable_sidecar_forbidden_stops_budget",
    "recovery_attempt_missing_evidence",
    "recovery_evidence_identity_mismatch",
]


class ABRecoveryRetryAuthorityV1(_FrozenModel):
    allowed: bool
    reason_code: RecoveryAuthorityReason
    previous_outcome: Literal["selected_pass", "candidate_failed", "unavailable", "execution_error"] | None


class ABRecoveryAttemptReservationV1(_FrozenModel):
    """One immutable reserve-before-provider ordinal."""

    schema_version: Literal["rag_token_chunk_recovery_attempt.v1"] = RECOVERY_ATTEMPT_SCHEMA_VERSION
    budget_id: Literal["phase64.4-plan12-live-selection-recovery"] = PLAN12_RECOVERY_BUDGET_ID
    budget_manifest_sha256: str = Field(pattern=_SHA256_PATTERN)
    ordinal: Literal[1, 2]
    reserved_at: datetime
    run_id: UUID
    selection_id: UUID
    candidate_state_sha256: str = Field(pattern=_SHA256_PATTERN)
    prerequisite_state_sha256: str = Field(pattern=_SHA256_PATTERN)
    authority_reason_code: Literal[
        "initial_attempt_allowed",
        "transient_execution_error_retry_allowed",
        "unavailable_prerequisite_change_retry_allowed",
    ]
    reservation_payload_sha256: str = Field(pattern=_SHA256_PATTERN)

    @model_validator(mode="after")
    def validate_reservation(self) -> ABRecoveryAttemptReservationV1:
        if self.reserved_at.tzinfo is None:
            raise ValueError("recovery_reservation_time_invalid")
        expected = _sha256_payload(self.model_dump(mode="json", exclude={"reservation_payload_sha256"}))
        if self.reservation_payload_sha256 != expected:
            raise ValueError("recovery_reservation_hash_mismatch")
        validate_safe_report_payload(self.model_dump(mode="json"))
        return self


class ABRecoveryAuthorizationV1(_FrozenModel):
    """Separate immutable proof that one selected pass consumed one fixed slot."""

    schema_version: Literal["rag_token_chunk_recovery_authorization.v1"] = RECOVERY_AUTHORIZATION_SCHEMA_VERSION
    authorized_at: datetime
    budget_id: Literal["phase64.4-plan12-live-selection-recovery"] = PLAN12_RECOVERY_BUDGET_ID
    budget_manifest_relative_path: str = Field(min_length=1, max_length=512)
    budget_manifest_sha256: str = Field(pattern=_SHA256_PATTERN)
    reservation_relative_path: str = Field(min_length=1, max_length=512)
    reservation_ordinal: Literal[1, 2]
    reservation_sha256: str = Field(pattern=_SHA256_PATTERN)
    candidate_state_relative_path: str = Field(min_length=1, max_length=512)
    candidate_state_sha256: str = Field(pattern=_SHA256_PATTERN)
    candidate_corpus_version_id: UUID
    candidate_run_token: UUID
    candidate_lease_owner: str = Field(min_length=1, max_length=128)
    candidate_config_schema_version: str = Field(min_length=1, max_length=128)
    candidate_config_fingerprint: str = Field(pattern=_SHA256_PATTERN)
    provider_parity_report_sha256: str = Field(pattern=_SHA256_PATTERN)
    source_manifest_revision_id: UUID
    source_manifest_revision: int = Field(gt=0)
    source_manifest_hash: str = Field(pattern=_SHA256_PATTERN)
    source_active_corpus_version_id: UUID
    source_rollout_epoch: int = Field(gt=0)
    expected_evidence_rollout_version: int = Field(ge=0)
    terminal_run_id: UUID
    terminal_run_sha256: str = Field(pattern=_SHA256_PATTERN)
    selection_id: UUID
    selection_sha256: str = Field(pattern=_SHA256_PATTERN)
    authorization_payload_sha256: str = Field(pattern=_SHA256_PATTERN)

    @model_validator(mode="after")
    def validate_authorization(self) -> ABRecoveryAuthorizationV1:
        if self.authorized_at.tzinfo is None:
            raise ValueError("recovery_authorization_time_invalid")
        expected_manifest_path = (Path("recovery-budgets") / self.budget_id / "manifest.json").as_posix()
        expected_reservation_path = (
            Path("recovery-budgets") / self.budget_id / "attempts" / f"{self.reservation_ordinal:02d}.json"
        ).as_posix()
        if (
            self.budget_manifest_relative_path != expected_manifest_path
            or self.reservation_relative_path != expected_reservation_path
        ):
            raise ValueError("recovery_authorization_path_invalid")
        expected = _sha256_payload(self.model_dump(mode="json", exclude={"authorization_payload_sha256"}))
        if self.authorization_payload_sha256 != expected:
            raise ValueError("recovery_authorization_hash_mismatch")
        validate_safe_report_payload(self.model_dump(mode="json"))
        return self


class CanonicalABActivationAuthorizationV1(_FrozenModel):
    """DB-lineage authorization emitted only for one selected-pass result."""

    schema_version: Literal["rag_token_chunk_db_activation_authorization.v1"] = (
        DB_ACTIVATION_AUTHORIZATION_SCHEMA_VERSION
    )
    authorized_at: datetime
    authority_id: UUID
    reservation_id: UUID
    result_id: UUID
    tenant_id: UUID
    candidate_corpus_version_id: UUID
    candidate_run_token: UUID
    terminal_run_id: UUID
    terminal_run_sha256: str = Field(pattern=_SHA256_PATTERN)
    selection_id: UUID
    selection_sha256: str = Field(pattern=_SHA256_PATTERN)
    authorization_payload_sha256: str = Field(pattern=_SHA256_PATTERN)

    @model_validator(mode="after")
    def validate_authorization(self) -> CanonicalABActivationAuthorizationV1:
        if self.authorized_at.tzinfo is None:
            raise ValueError("db_activation_authorization_time_invalid")
        expected = _sha256_payload(self.model_dump(mode="json", exclude={"authorization_payload_sha256"}))
        if expected != self.authorization_payload_sha256:
            raise ValueError("db_activation_authorization_hash_mismatch")
        validate_safe_report_payload(self.model_dump(mode="json"))
        return self


@dataclass(frozen=True, slots=True)
class ImmutableRecoveryBudgetManifestV1:
    path: Path
    sha256: str


@dataclass(frozen=True, slots=True)
class ImmutableRecoveryAuthorizationV1:
    path: Path
    sha256: str


def write_db_activation_authorization_create_only(
    *,
    root: Path,
    report: TerminalABRunV1,
    binding: ABSelectionBindingV1,
    authority_id: UUID,
    reservation_id: UUID,
    result_id: UUID,
    terminal_run_sha256: str,
    selection_sha256: str,
) -> ImmutableRecoveryAuthorizationV1:
    """Create the additive DB-backed activation proof for selected-pass only."""

    if (
        report.outcome != "selected_pass"
        or binding.tenant_id != report.runtime.tenant_id
        or binding.candidate_corpus_version_id != report.runtime.candidate.corpus_version_id
    ):
        raise ValueError("selected_pass_required")
    base: dict[str, Any] = {
        "schema_version": DB_ACTIVATION_AUTHORIZATION_SCHEMA_VERSION,
        "authorized_at": report.generated_at,
        "authority_id": authority_id,
        "reservation_id": reservation_id,
        "result_id": result_id,
        "tenant_id": binding.tenant_id,
        "candidate_corpus_version_id": binding.candidate_corpus_version_id,
        "candidate_run_token": binding.candidate_run_token,
        "terminal_run_id": report.run_id,
        "terminal_run_sha256": terminal_run_sha256,
        "selection_id": binding.selection_id,
        "selection_sha256": selection_sha256,
    }
    authorization = CanonicalABActivationAuthorizationV1(
        **base,
        authorization_payload_sha256=_sha256_payload(
            CanonicalABActivationAuthorizationV1.model_construct(
                **base,
                authorization_payload_sha256="sha256:" + "0" * 64,
            ).model_dump(mode="json", exclude={"authorization_payload_sha256"})
        ),
    )
    payload = canonical_report_json_bytes(authorization.model_dump(mode="json"))
    path = root / "db-activation-authorizations" / f"{binding.selection_id}.json"
    _write_create_only_bytes(path, payload)
    return ImmutableRecoveryAuthorizationV1(path=path, sha256=_sha256_bytes(payload))


class RecoveryLiveAuthorityProofV1(_FrozenModel):
    """Source-backed DB proof required before a recovery budget can exist."""

    tenant_id: UUID
    incumbent_corpus_version_id: UUID
    candidate_corpus_version_id: UUID
    candidate_run_token: UUID
    candidate_lease_owner: str = Field(min_length=1, max_length=128)
    candidate_state_version: int = Field(gt=0)
    source_manifest_revision_id: UUID
    source_manifest_revision: int = Field(gt=0)
    source_manifest_hash: str = Field(pattern=_SHA256_PATTERN)
    source_rollout_epoch: int = Field(gt=0)
    expected_evidence_rollout_version: int = Field(ge=0)
    deterministic_rebuild_sha256: str = Field(pattern=_SHA256_PATTERN)
    complete_projection_proved: bool
    sealed_inputs_proved: bool


ExecutionBundleFaultInjector = Callable[[str], None]


def build_plan12_recovery_budget_manifest(
    *,
    created_at: datetime,
    tenant_id: UUID,
    incumbent_corpus_version_id: UUID,
    candidate_corpus_version_id: UUID,
    candidate_run_token: UUID,
    candidate_lease_owner: str,
    candidate_state_version: int,
    candidate_state_relative_path: str,
    candidate_state_sha256: str,
    candidate_recovery_descriptor_sha256: str,
    candidate_config_schema_version: str,
    candidate_config_fingerprint: str,
    candidate_source_manifest_revision_id: UUID,
    candidate_source_manifest_revision: int,
    candidate_source_manifest_hash: str,
    candidate_source_active_corpus_version_id: UUID,
    candidate_source_rollout_epoch: int,
    candidate_expected_evidence_rollout_version: int,
    provider_parity_run_id: UUID,
    provider_parity_report_sha256: str,
    provider_parity_config_fingerprint: str,
    provider_parity_probe_fixture_sha256: str,
    provider_parity_submitted_content_sha256: str,
) -> ABRecoveryBudgetManifestV1:
    base: dict[str, Any] = {
        "schema_version": RECOVERY_BUDGET_SCHEMA_VERSION,
        "budget_id": PLAN12_RECOVERY_BUDGET_ID,
        "phase": "64.4",
        "plan": "12",
        "created_at": created_at,
        "max_attempts": _PLAN12_MAX_ATTEMPTS,
        "plan10_terminal_runs": PLAN10_TERMINAL_RUNS,
        "plan10_baseline_proof_sha256": PLAN10_BASELINE_PROOF_SHA256,
        "tenant_id": tenant_id,
        "incumbent_corpus_version_id": incumbent_corpus_version_id,
        "candidate_corpus_version_id": candidate_corpus_version_id,
        "candidate_run_token": candidate_run_token,
        "candidate_lease_owner": candidate_lease_owner,
        "candidate_state_version": candidate_state_version,
        "candidate_state_relative_path": candidate_state_relative_path,
        "candidate_state_sha256": candidate_state_sha256,
        "candidate_recovery_descriptor_sha256": candidate_recovery_descriptor_sha256,
        "candidate_config_schema_version": candidate_config_schema_version,
        "candidate_config_fingerprint": candidate_config_fingerprint,
        "candidate_source_manifest_revision_id": candidate_source_manifest_revision_id,
        "candidate_source_manifest_revision": candidate_source_manifest_revision,
        "candidate_source_manifest_hash": candidate_source_manifest_hash,
        "candidate_source_active_corpus_version_id": candidate_source_active_corpus_version_id,
        "candidate_source_rollout_epoch": candidate_source_rollout_epoch,
        "candidate_expected_evidence_rollout_version": candidate_expected_evidence_rollout_version,
        "provider_parity_run_id": provider_parity_run_id,
        "provider_parity_report_sha256": provider_parity_report_sha256,
        "provider_parity_config_fingerprint": provider_parity_config_fingerprint,
        "provider_parity_probe_fixture_sha256": provider_parity_probe_fixture_sha256,
        "provider_parity_submitted_content_sha256": provider_parity_submitted_content_sha256,
        "provider": "dashscope",
        "embedding_model": "text-embedding-v4",
        "embedding_dimensions": 1024,
        "max_embedding_tokens": _PLAN12_MAX_EMBEDDING_TOKENS,
        "target_embedding_tokens": _PLAN12_TARGET_EMBEDDING_TOKENS,
        "overlap_tokens": _PLAN12_OVERLAP_TOKENS,
        "manifest_hash": SEALED_MANIFEST_HASH,
        "gold_hash": SEALED_GOLD_HASH,
        "dataset_baseline_identity": SEALED_DATASET_BASELINE_IDENTITY,
    }
    return ABRecoveryBudgetManifestV1(
        **base,
        manifest_payload_sha256=_sha256_payload(
            ABRecoveryBudgetManifestV1.model_construct(
                **base,
                manifest_payload_sha256="sha256:" + "0" * 64,
            ).model_dump(mode="json", exclude={"manifest_payload_sha256"})
        ),
    )


def write_recovery_budget_manifest_create_only(
    manifest: ABRecoveryBudgetManifestV1,
    *,
    root: Path,
) -> ImmutableRecoveryBudgetManifestV1:
    validated = ABRecoveryBudgetManifestV1.model_validate(manifest.model_dump(mode="json"))
    payload = canonical_report_json_bytes(validated.model_dump(mode="json"))
    path = root / "recovery-budgets" / validated.budget_id / "manifest.json"
    if path.exists():
        try:
            existing = path.read_bytes()
        except OSError:
            raise ValueError("create_conflict") from None
        if existing != payload:
            raise ValueError("create_conflict")
        _fsync_directory(path.parent)
    else:
        try:
            _write_create_only_bytes(path, payload)
        except ValueError as error:
            try:
                existing = path.read_bytes()
            except OSError:
                existing = b""
            if str(error) != "create_conflict" or existing != payload:
                raise
            _fsync_directory(path.parent)
    return ImmutableRecoveryBudgetManifestV1(path=path, sha256=_sha256_bytes(payload))


def issue_canonical_recovery_budget_manifest(
    *,
    root: Path,
    candidate_state_path: Path,
    provider_parity_report_path: Path,
    checked_at: datetime,
    live_authority: RecoveryLiveAuthorityProofV1,
) -> ImmutableRecoveryBudgetManifestV1:
    """Issue or reconcile the sole fixed budget after all live authority gates."""

    identity, descriptor, parity_sha256, parity = _load_recovery_issuance_authority(
        root=root,
        candidate_state_path=candidate_state_path,
        provider_parity_report_path=provider_parity_report_path,
        checked_at=checked_at,
    )
    if identity.state != "complete":
        raise RecoveryAttemptRefused("recovery_candidate_incomplete")
    expected_live = {
        "tenant_id": identity.tenant_id,
        "incumbent_corpus_version_id": identity.source_active_corpus_version_id,
        "candidate_corpus_version_id": identity.corpus_version_id,
        "candidate_run_token": identity.run_token,
        "candidate_lease_owner": identity.lease_owner,
        "candidate_state_version": identity.state_version,
        "source_manifest_revision_id": identity.source_manifest_revision_id,
        "source_manifest_revision": identity.source_manifest_revision,
        "source_manifest_hash": identity.source_manifest_hash,
        "source_rollout_epoch": identity.source_rollout_epoch,
        "expected_evidence_rollout_version": identity.expected_evidence_rollout_version,
    }
    if (
        any(getattr(live_authority, key) != value for key, value in expected_live.items())
        or not live_authority.complete_projection_proved
        or not live_authority.sealed_inputs_proved
    ):
        raise RecoveryAttemptRefused("recovery_live_authority_mismatch")

    path = root / "recovery-budgets" / PLAN12_RECOVERY_BUDGET_ID / "manifest.json"
    existing: ABRecoveryBudgetManifestV1 | None = None
    if path.exists():
        try:
            existing = load_recovery_budget_manifest(path)
        except ValueError:
            raise RecoveryAttemptRefused("recovery_budget_invalid") from None
    created_at = existing.created_at if existing is not None else checked_at
    manifest = build_plan12_recovery_budget_manifest(
        created_at=created_at,
        tenant_id=identity.tenant_id,
        incumbent_corpus_version_id=identity.source_active_corpus_version_id,
        candidate_corpus_version_id=identity.corpus_version_id,
        candidate_run_token=identity.run_token,
        candidate_lease_owner=identity.lease_owner,
        candidate_state_version=identity.state_version,
        candidate_state_relative_path=candidate_state_path.relative_to(root).as_posix(),
        candidate_state_sha256=_sha256_bytes(candidate_state_path.read_bytes()),
        candidate_recovery_descriptor_sha256=_sha256_bytes(
            policy_reindex_descriptor_path(
                root / "candidates",
                tenant_id=identity.tenant_id,
                run_token=identity.run_token,
            ).read_bytes()
        ),
        candidate_config_schema_version=identity.config_schema_version,
        candidate_config_fingerprint=identity.config_fingerprint,
        candidate_source_manifest_revision_id=identity.source_manifest_revision_id,
        candidate_source_manifest_revision=identity.source_manifest_revision,
        candidate_source_manifest_hash=identity.source_manifest_hash,
        candidate_source_active_corpus_version_id=identity.source_active_corpus_version_id,
        candidate_source_rollout_epoch=identity.source_rollout_epoch,
        candidate_expected_evidence_rollout_version=identity.expected_evidence_rollout_version,
        provider_parity_run_id=parity.run_id,
        provider_parity_report_sha256=parity_sha256,
        provider_parity_config_fingerprint=parity.config_fingerprint,
        provider_parity_probe_fixture_sha256=parity.probe_fixture_sha256,
        provider_parity_submitted_content_sha256=parity.submitted_content_sha256,
    )
    try:
        return write_recovery_budget_manifest_create_only(manifest, root=root)
    except (OSError, ValueError):
        raise RecoveryAttemptRefused("recovery_budget_conflict") from None


def load_recovery_budget_manifest(path: Path) -> ABRecoveryBudgetManifestV1:
    try:
        return ABRecoveryBudgetManifestV1.model_validate_json(path.read_bytes())
    except (OSError, ValidationError, ValueError):
        raise ValueError("recovery_budget_invalid") from None


def load_recovery_attempt_reservation(
    path: Path,
    *,
    manifest: ABRecoveryBudgetManifestV1,
    manifest_sha256: str,
) -> ABRecoveryAttemptReservationV1:
    try:
        reservation = ABRecoveryAttemptReservationV1.model_validate_json(path.read_bytes())
    except (OSError, ValidationError, ValueError):
        raise ValueError("recovery_reservation_invalid") from None
    if (
        reservation.budget_id != manifest.budget_id
        or reservation.budget_manifest_sha256 != manifest_sha256
        or reservation.ordinal != int(path.stem)
    ):
        raise ValueError("recovery_reservation_invalid")
    return reservation


def write_recovery_authorization_create_only(
    *,
    root: Path,
    manifest_path: Path,
    reservation_path: Path,
    candidate_state_path: Path,
    provider_parity_report_path: Path,
    terminal_run_path: Path,
    selection_path: Path,
    checked_at: datetime,
) -> ImmutableRecoveryAuthorizationV1:
    """Publish or byte-identically reconcile one selected recovery lineage."""

    lineage = _load_recovery_authorization_lineage(
        root=root,
        manifest_path=manifest_path,
        reservation_path=reservation_path,
        candidate_state_path=candidate_state_path,
        provider_parity_report_path=provider_parity_report_path,
        terminal_run_path=terminal_run_path,
        selection_path=selection_path,
        checked_at=checked_at,
    )
    (
        manifest,
        manifest_sha256,
        reservation,
        reservation_sha256,
        terminal,
        terminal_sha256,
        selection,
        selection_sha256,
    ) = lineage
    base: dict[str, Any] = {
        "schema_version": RECOVERY_AUTHORIZATION_SCHEMA_VERSION,
        "authorized_at": checked_at,
        "budget_id": manifest.budget_id,
        "budget_manifest_relative_path": manifest_path.relative_to(root).as_posix(),
        "budget_manifest_sha256": manifest_sha256,
        "reservation_relative_path": reservation_path.relative_to(root).as_posix(),
        "reservation_ordinal": reservation.ordinal,
        "reservation_sha256": reservation_sha256,
        "candidate_state_relative_path": manifest.candidate_state_relative_path,
        "candidate_state_sha256": manifest.candidate_state_sha256,
        "candidate_corpus_version_id": manifest.candidate_corpus_version_id,
        "candidate_run_token": manifest.candidate_run_token,
        "candidate_lease_owner": manifest.candidate_lease_owner,
        "candidate_config_schema_version": manifest.candidate_config_schema_version,
        "candidate_config_fingerprint": manifest.candidate_config_fingerprint,
        "provider_parity_report_sha256": manifest.provider_parity_report_sha256,
        "source_manifest_revision_id": manifest.candidate_source_manifest_revision_id,
        "source_manifest_revision": manifest.candidate_source_manifest_revision,
        "source_manifest_hash": manifest.candidate_source_manifest_hash,
        "source_active_corpus_version_id": manifest.candidate_source_active_corpus_version_id,
        "source_rollout_epoch": manifest.candidate_source_rollout_epoch,
        "expected_evidence_rollout_version": manifest.candidate_expected_evidence_rollout_version,
        "terminal_run_id": terminal.run_id,
        "terminal_run_sha256": terminal_sha256,
        "selection_id": selection.selection_id,
        "selection_sha256": selection_sha256,
    }
    authorization = ABRecoveryAuthorizationV1(
        **base,
        authorization_payload_sha256=_sha256_payload(
            ABRecoveryAuthorizationV1.model_construct(
                **base,
                authorization_payload_sha256="sha256:" + "0" * 64,
            ).model_dump(mode="json", exclude={"authorization_payload_sha256"})
        ),
    )
    payload = canonical_report_json_bytes(authorization.model_dump(mode="json"))
    path = root / "recovery-authorizations" / f"{selection.selection_id}.json"
    if path.exists():
        try:
            if path.read_bytes() != payload:
                raise ValueError("recovery_authorization_conflict")
        except OSError:
            raise ValueError("recovery_authorization_conflict") from None
    else:
        try:
            _write_create_only_bytes(path, payload)
        except ValueError as error:
            if path.exists() and _read_bytes_or_conflict(path) == payload:
                pass
            else:
                raise ValueError("recovery_authorization_conflict") from error
    return ImmutableRecoveryAuthorizationV1(path=path, sha256=_sha256_bytes(payload))


def load_recovery_authorization(
    path: Path,
    *,
    root: Path | None = None,
    manifest_path: Path | None = None,
    reservation_path: Path | None = None,
    candidate_state_path: Path | None = None,
    provider_parity_report_path: Path | None = None,
    terminal_run_path: Path | None = None,
    selection_path: Path | None = None,
    checked_at: datetime | None = None,
) -> ABRecoveryAuthorizationV1:
    """Load one authorization, optionally proving every referenced immutable byte."""

    try:
        payload = path.read_bytes()
        authorization = ABRecoveryAuthorizationV1.model_validate_json(payload)
    except (OSError, ValidationError, ValueError):
        raise ValueError("recovery_authorization_invalid") from None
    strict_values = (
        root,
        manifest_path,
        reservation_path,
        candidate_state_path,
        provider_parity_report_path,
        terminal_run_path,
        selection_path,
        checked_at,
    )
    if all(value is None for value in strict_values):
        return authorization
    if any(value is None for value in strict_values):
        raise ValueError("recovery_authorization_invalid")
    assert root is not None
    assert manifest_path is not None
    assert reservation_path is not None
    assert candidate_state_path is not None
    assert provider_parity_report_path is not None
    assert terminal_run_path is not None
    assert selection_path is not None
    assert checked_at is not None
    expected_path = root / "recovery-authorizations" / f"{authorization.selection_id}.json"
    if path.absolute() != expected_path.absolute() or _path_uses_symlink(root=root, path=path):
        raise ValueError("recovery_authorization_invalid")
    lineage = _load_recovery_authorization_lineage(
        root=root,
        manifest_path=manifest_path,
        reservation_path=reservation_path,
        candidate_state_path=candidate_state_path,
        provider_parity_report_path=provider_parity_report_path,
        terminal_run_path=terminal_run_path,
        selection_path=selection_path,
        checked_at=checked_at,
    )
    (
        manifest,
        manifest_sha256,
        reservation,
        reservation_sha256,
        terminal,
        terminal_sha256,
        selection,
        selection_sha256,
    ) = lineage
    expected = {
        "authorized_at": checked_at,
        "budget_id": manifest.budget_id,
        "budget_manifest_relative_path": manifest_path.relative_to(root).as_posix(),
        "budget_manifest_sha256": manifest_sha256,
        "reservation_relative_path": reservation_path.relative_to(root).as_posix(),
        "reservation_ordinal": reservation.ordinal,
        "reservation_sha256": reservation_sha256,
        "candidate_state_relative_path": manifest.candidate_state_relative_path,
        "candidate_state_sha256": manifest.candidate_state_sha256,
        "candidate_corpus_version_id": manifest.candidate_corpus_version_id,
        "candidate_run_token": manifest.candidate_run_token,
        "candidate_lease_owner": manifest.candidate_lease_owner,
        "candidate_config_schema_version": manifest.candidate_config_schema_version,
        "candidate_config_fingerprint": manifest.candidate_config_fingerprint,
        "provider_parity_report_sha256": manifest.provider_parity_report_sha256,
        "source_manifest_revision_id": manifest.candidate_source_manifest_revision_id,
        "source_manifest_revision": manifest.candidate_source_manifest_revision,
        "source_manifest_hash": manifest.candidate_source_manifest_hash,
        "source_active_corpus_version_id": manifest.candidate_source_active_corpus_version_id,
        "source_rollout_epoch": manifest.candidate_source_rollout_epoch,
        "expected_evidence_rollout_version": manifest.candidate_expected_evidence_rollout_version,
        "terminal_run_id": terminal.run_id,
        "terminal_run_sha256": terminal_sha256,
        "selection_id": selection.selection_id,
        "selection_sha256": selection_sha256,
    }
    if any(getattr(authorization, key) != value for key, value in expected.items()):
        raise ValueError("recovery_authorization_invalid")
    return authorization


def _load_recovery_authorization_lineage(
    *,
    root: Path,
    manifest_path: Path,
    reservation_path: Path,
    candidate_state_path: Path,
    provider_parity_report_path: Path,
    terminal_run_path: Path,
    selection_path: Path,
    checked_at: datetime,
) -> tuple[
    ABRecoveryBudgetManifestV1,
    str,
    ABRecoveryAttemptReservationV1,
    str,
    TerminalABRunV1,
    str,
    ABSelectionDecisionV1,
    str,
]:
    try:
        manifest_payload = manifest_path.read_bytes()
        manifest = ABRecoveryBudgetManifestV1.model_validate_json(manifest_payload)
    except (OSError, ValidationError, ValueError):
        raise ValueError("recovery_authorization_lineage_invalid") from None
    expected_manifest_path = root / "recovery-budgets" / manifest.budget_id / "manifest.json"
    if manifest_path.absolute() != expected_manifest_path.absolute() or _path_uses_symlink(
        root=root, path=manifest_path
    ):
        raise ValueError("recovery_authorization_lineage_invalid")
    manifest_sha256 = _sha256_bytes(manifest_payload)
    expected_reservation_path = manifest_path.parent / "attempts" / f"{int(reservation_path.stem):02d}.json"
    if reservation_path.absolute() != expected_reservation_path.absolute() or _path_uses_symlink(
        root=root, path=reservation_path
    ):
        raise ValueError("recovery_authorization_lineage_invalid")
    try:
        reservation_payload = reservation_path.read_bytes()
        reservation = load_recovery_attempt_reservation(
            reservation_path,
            manifest=manifest,
            manifest_sha256=manifest_sha256,
        )
    except (OSError, ValueError):
        raise ValueError("recovery_authorization_lineage_invalid") from None
    load_recovery_candidate_state(
        manifest=manifest,
        root=root,
        candidate_state_path=candidate_state_path,
        provider_parity_report_path=provider_parity_report_path,
        checked_at=checked_at,
    )
    try:
        terminal_payload = terminal_run_path.read_bytes()
        terminal = load_terminal_ab_run(terminal_run_path)
        selection_payload = selection_path.read_bytes()
        selection = load_selection_decision(selection_path)
    except (OSError, ValidationError, ValueError):
        raise ValueError("recovery_authorization_lineage_invalid") from None
    terminal_sha256 = _sha256_bytes(terminal_payload)
    selection_sha256 = _sha256_bytes(selection_payload)
    expected_terminal_path = root / "runs" / f"{reservation.run_id}.json"
    expected_selection_path = root / "selections" / f"{reservation.selection_id}.json"
    if (
        terminal_run_path.absolute() != expected_terminal_path.absolute()
        or selection_path.absolute() != expected_selection_path.absolute()
        or _path_uses_symlink(root=root, path=terminal_run_path)
        or _path_uses_symlink(root=root, path=selection_path)
        or reservation.candidate_state_sha256 != manifest.candidate_state_sha256
        or terminal.outcome != "selected_pass"
        or not _recovery_report_matches_manifest(terminal, manifest=manifest, expected_run_id=reservation.run_id)
        or selection.selection_id != reservation.selection_id
        or selection.terminal_run_id != terminal.run_id
        or selection.terminal_run_sha256 != terminal_sha256
        or selection.provider_parity_report_sha256 != manifest.provider_parity_report_sha256
        or selection.tenant_id != manifest.tenant_id
        or selection.candidate_corpus_version_id != manifest.candidate_corpus_version_id
        or selection.candidate_run_token != manifest.candidate_run_token
        or selection.candidate_lease_owner != manifest.candidate_lease_owner
        or selection.source_manifest_hash != manifest.candidate_source_manifest_hash
    ):
        raise ValueError("recovery_authorization_lineage_invalid")
    return (
        manifest,
        manifest_sha256,
        reservation,
        _sha256_bytes(reservation_payload),
        terminal,
        terminal_sha256,
        selection,
        selection_sha256,
    )


def validate_fixed_plan10_evidence(root: Path) -> tuple[RecoveryPriorRunV1, ...]:
    """Strictly prove the three immutable exhausted Plan10 runs."""

    for expected in PLAN10_TERMINAL_RUNS:
        path = root / "runs" / f"{expected.run_id}.json"
        try:
            payload = path.read_bytes()
            report = TerminalABRunV1.model_validate_json(payload)
        except (OSError, ValidationError, ValueError):
            raise ValueError("plan10_terminal_evidence_invalid") from None
        if (
            _sha256_bytes(payload) != expected.terminal_run_sha256
            or report.run_id != expected.run_id
            or report.outcome != "execution_error"
            or report.runtime.execution_kind != "full_provider"
        ):
            raise ValueError("plan10_terminal_evidence_invalid")
    return PLAN10_TERMINAL_RUNS


def evaluate_recovery_retry_authority(
    *,
    manifest: ABRecoveryBudgetManifestV1,
    previous_reservation: ABRecoveryAttemptReservationV1,
    root: Path,
    next_prerequisite_state_sha256: str,
) -> ABRecoveryRetryAuthorityV1:
    """Evaluate the closed Plan12 retry matrix from immutable evidence only."""

    if (
        previous_reservation.budget_id != manifest.budget_id
        or previous_reservation.ordinal != 1
        or not _valid_sha256(next_prerequisite_state_sha256)
    ):
        return _recovery_authority(False, "recovery_evidence_identity_mismatch", None)
    run_path = root / "runs" / f"{previous_reservation.run_id}.json"
    try:
        run_payload = run_path.read_bytes()
        report = TerminalABRunV1.model_validate_json(run_payload)
    except (OSError, ValidationError, ValueError):
        return _recovery_authority(False, "recovery_attempt_missing_evidence", None)
    if not _recovery_report_matches_manifest(
        report,
        manifest=manifest,
        expected_run_id=previous_reservation.run_id,
    ):
        return _recovery_authority(False, "recovery_evidence_identity_mismatch", report.outcome)

    if report.outcome == "selected_pass":
        return _recovery_authority(False, "selected_pass_stops_budget", report.outcome)
    if report.outcome == "candidate_failed":
        return _recovery_authority(False, "candidate_failed_stops_budget", report.outcome)
    if report.outcome == "execution_error":
        try:
            bundle = load_execution_error_bundle(root=root, run_id=report.run_id)
        except ValueError:
            return _recovery_authority(False, "execution_evidence_invalid_stops_budget", report.outcome)
        if bundle.report != report or bundle.manifest.terminal_run_sha256 != _sha256_bytes(run_payload):
            return _recovery_authority(False, "execution_evidence_invalid_stops_budget", report.outcome)
        diagnostic = bundle.diagnostic
        if not diagnostic.outer_rollback_proved:
            return _recovery_authority(False, "rollback_unproved_stops_budget", report.outcome)
        transient = (
            (diagnostic.stage, diagnostic.reason_code) == _TRANSIENT_EXECUTION_RETRY
            and diagnostic.provider_availability == "available"
            and diagnostic.provider_request_classification == "request_failed"
            and diagnostic.provider_request_count > 0
        )
        if not transient:
            return _recovery_authority(False, "implementation_defect_stops_budget", report.outcome)
        return _recovery_authority(True, "transient_execution_error_retry_allowed", report.outcome)

    if _recovery_unavailable_has_sidecar(root=root, run_id=report.run_id):
        return _recovery_authority(False, "unavailable_sidecar_forbidden_stops_budget", report.outcome)
    if len(report.safe_reason_codes) != 1 or report.safe_reason_codes[0] not in _UNAVAILABLE_RETRY_REASONS:
        return _recovery_authority(False, "unavailable_reason_not_allowlisted_stops_budget", report.outcome)
    if next_prerequisite_state_sha256 == previous_reservation.prerequisite_state_sha256:
        return _recovery_authority(False, "prerequisite_state_unchanged_stops_budget", report.outcome)
    return _recovery_authority(True, "unavailable_prerequisite_change_retry_allowed", report.outcome)


def require_current_recovery_authority(
    *,
    identity: PolicyReindexRunIdentity,
    checked_at: datetime,
) -> None:
    """Require one aware UTC instant to precede both immutable expiries."""

    if checked_at.tzinfo is None:
        raise RecoveryAttemptRefused("recovery_authority_expired")
    current = checked_at.astimezone(UTC)
    if (
        current >= identity.lease_expires_at.astimezone(UTC)
        or current >= identity.parity_expires_at.astimezone(UTC)
        or current < identity.parity_captured_at.astimezone(UTC)
    ):
        raise RecoveryAttemptRefused("recovery_authority_expired")


def _load_recovery_issuance_authority(
    *,
    root: Path,
    candidate_state_path: Path,
    provider_parity_report_path: Path,
    checked_at: datetime,
) -> tuple[PolicyReindexRunIdentity, Any, str, Any]:
    candidates_root = root / "candidates"
    try:
        relative = candidate_state_path.absolute().relative_to(root.absolute())
    except ValueError:
        raise RecoveryAttemptRefused("recovery_candidate_state_identity_mismatch") from None
    parts = relative.parts
    if (
        len(parts) != 7
        or parts[0] != "candidates"
        or parts[1] != "tenants"
        or parts[3] != "runs"
        or parts[5] != "states"
        or not parts[6].endswith(".json")
    ):
        raise RecoveryAttemptRefused("recovery_candidate_state_identity_mismatch")
    try:
        tenant_id = UUID(parts[2])
        run_token = UUID(parts[4])
        state_version = int(Path(parts[6]).stem)
    except (TypeError, ValueError):
        raise RecoveryAttemptRefused("recovery_candidate_state_identity_mismatch") from None
    if state_version <= 0 or _path_uses_symlink(root=root, path=candidate_state_path):
        raise RecoveryAttemptRefused("recovery_candidate_state_identity_mismatch")
    descriptor_path = policy_reindex_descriptor_path(
        candidates_root,
        tenant_id=tenant_id,
        run_token=run_token,
    )
    if _path_uses_symlink(root=root, path=descriptor_path):
        raise RecoveryAttemptRefused("recovery_candidate_state_invalid")
    try:
        descriptor = load_policy_reindex_recovery_descriptor(descriptor_path, root=candidates_root)
        identity = load_policy_reindex_state(
            candidate_state_path,
            descriptor=descriptor,
            root=candidates_root,
        )
    except (OSError, PolicyReindexArtifactError):
        raise RecoveryAttemptRefused("recovery_candidate_state_invalid") from None
    if identity.state_version != state_version:
        raise RecoveryAttemptRefused("recovery_candidate_state_identity_mismatch")
    require_current_recovery_authority(identity=identity, checked_at=checked_at)

    if provider_parity_report_path.is_symlink():
        raise RecoveryAttemptRefused("recovery_parity_invalid")
    try:
        parity_payload = provider_parity_report_path.read_bytes()
        parity = load_parity_report(provider_parity_report_path)
    except (OSError, TokenizerParityError):
        raise RecoveryAttemptRefused("recovery_parity_invalid") from None
    parity_sha256 = _sha256_bytes(parity_payload)
    if (
        parity_sha256 != descriptor.parity_report_sha256
        or parity.provider_parity_status is not ProviderParityStatus.PASSED
        or parity.reason_code != "exact_match"
        or parity.config_fingerprint != descriptor.parity_config_fingerprint
        or parity.probe_fixture_sha256 != descriptor.parity_probe_fixture_sha256
        or parity.submitted_content_sha256 != descriptor.parity_submitted_content_sha256
        or parity.captured_at != descriptor.parity_captured_at
        or parity.provider != "dashscope"
        or parity.model != "text-embedding-v4"
        or parity.dimensions != 1024
    ):
        raise RecoveryAttemptRefused("recovery_parity_invalid")
    return identity, descriptor, parity_sha256, parity


def load_recovery_issuance_identity(
    *,
    root: Path,
    candidate_state_path: Path,
    provider_parity_report_path: Path,
    checked_at: datetime,
) -> PolicyReindexRunIdentity:
    """Strict-load issuance inputs before the caller obtains live DB proof."""

    identity, _, _, _ = _load_recovery_issuance_authority(
        root=root,
        candidate_state_path=candidate_state_path,
        provider_parity_report_path=provider_parity_report_path,
        checked_at=checked_at,
    )
    return identity


def load_recovery_candidate_state(
    *,
    manifest: ABRecoveryBudgetManifestV1,
    root: Path,
    candidate_state_path: Path,
    provider_parity_report_path: Path,
    checked_at: datetime,
) -> PolicyReindexRunIdentity:
    """Strict-load the exact candidate and fresh parity bound by a budget."""

    expected_state_path = root / manifest.candidate_state_relative_path
    if candidate_state_path.absolute() != expected_state_path.absolute() or _path_uses_symlink(
        root=root, path=candidate_state_path
    ):
        raise RecoveryAttemptRefused("recovery_candidate_state_identity_mismatch")
    try:
        candidate_payload = candidate_state_path.read_bytes()
    except OSError:
        raise RecoveryAttemptRefused("recovery_candidate_state_invalid") from None
    if _sha256_bytes(candidate_payload) != manifest.candidate_state_sha256:
        raise RecoveryAttemptRefused("recovery_candidate_state_invalid")

    candidates_root = root / "candidates"
    descriptor_path = policy_reindex_descriptor_path(
        candidates_root,
        tenant_id=manifest.tenant_id,
        run_token=manifest.candidate_run_token,
    )
    if _path_uses_symlink(root=root, path=descriptor_path):
        raise RecoveryAttemptRefused("recovery_candidate_state_invalid")
    try:
        descriptor_payload = descriptor_path.read_bytes()
        descriptor = load_policy_reindex_recovery_descriptor(descriptor_path, root=candidates_root)
        identity = load_policy_reindex_state(
            candidate_state_path,
            descriptor=descriptor,
            root=candidates_root,
        )
    except (OSError, PolicyReindexArtifactError):
        raise RecoveryAttemptRefused("recovery_candidate_state_invalid") from None
    if _sha256_bytes(descriptor_payload) != manifest.candidate_recovery_descriptor_sha256:
        raise RecoveryAttemptRefused("recovery_candidate_state_invalid")
    if not _candidate_identity_matches_manifest(identity, manifest=manifest):
        raise RecoveryAttemptRefused("recovery_candidate_state_identity_mismatch")
    require_current_recovery_authority(identity=identity, checked_at=checked_at)

    if provider_parity_report_path.is_symlink():
        raise RecoveryAttemptRefused("recovery_parity_invalid")
    try:
        parity_payload = provider_parity_report_path.read_bytes()
        parity = load_parity_report(provider_parity_report_path)
    except (OSError, TokenizerParityError):
        raise RecoveryAttemptRefused("recovery_parity_invalid") from None
    age = checked_at.astimezone(UTC) - parity.captured_at.astimezone(UTC)
    if (
        _sha256_bytes(parity_payload) != manifest.provider_parity_report_sha256
        or parity.provider_parity_status is not ProviderParityStatus.PASSED
        or parity.reason_code != "exact_match"
        or not timedelta(0) <= age <= _FRESH_PARITY_MAXIMUM_AGE
        or parity.run_id != manifest.provider_parity_run_id
        or parity.config_fingerprint != manifest.provider_parity_config_fingerprint
        or parity.probe_fixture_sha256 != manifest.provider_parity_probe_fixture_sha256
        or parity.submitted_content_sha256 != manifest.provider_parity_submitted_content_sha256
        or parity.provider != manifest.provider
        or parity.model != manifest.embedding_model
        or parity.dimensions != manifest.embedding_dimensions
    ):
        raise RecoveryAttemptRefused("recovery_parity_invalid")
    return identity


def _candidate_identity_matches_manifest(
    identity: PolicyReindexRunIdentity,
    *,
    manifest: ABRecoveryBudgetManifestV1,
) -> bool:
    return (
        identity.state == "complete"
        and identity.tenant_id == manifest.tenant_id
        and identity.corpus_version_id == manifest.candidate_corpus_version_id
        and identity.run_token == manifest.candidate_run_token
        and identity.lease_owner == manifest.candidate_lease_owner
        and identity.state_version == manifest.candidate_state_version
        and identity.config_schema_version == manifest.candidate_config_schema_version
        and identity.config_fingerprint == manifest.candidate_config_fingerprint
        and identity.provider_parity_report_hash == manifest.provider_parity_report_sha256
        and identity.source_manifest_revision_id == manifest.candidate_source_manifest_revision_id
        and identity.source_manifest_revision == manifest.candidate_source_manifest_revision
        and identity.source_manifest_hash == manifest.candidate_source_manifest_hash
        and identity.source_active_corpus_version_id == manifest.candidate_source_active_corpus_version_id
        and identity.source_active_corpus_version_id == manifest.incumbent_corpus_version_id
        and identity.source_rollout_epoch == manifest.candidate_source_rollout_epoch
        and identity.expected_evidence_rollout_version == manifest.candidate_expected_evidence_rollout_version
    )


def _path_uses_symlink(*, root: Path, path: Path) -> bool:
    try:
        relative = path.absolute().relative_to(root.absolute())
    except ValueError:
        return True
    current = root.absolute()
    for part in relative.parts:
        current = current / part
        if current.exists() and current.is_symlink():
            return True
    return False


def reserve_recovery_attempt(
    *,
    manifest_path: Path,
    root: Path,
    candidate_state_path: Path,
    provider_parity_report_path: Path,
    run_id: UUID,
    selection_id: UUID,
    reserved_at: datetime,
    prerequisite_state_sha256: str,
) -> ABRecoveryAttemptReservationV1:
    """Atomically consume one fixed ordinal before constructing the provider."""

    try:
        manifest_payload = manifest_path.read_bytes()
        manifest = ABRecoveryBudgetManifestV1.model_validate_json(manifest_payload)
    except (OSError, ValidationError, ValueError):
        raise RecoveryAttemptRefused("recovery_budget_invalid") from None
    expected_manifest_path = root / "recovery-budgets" / manifest.budget_id / "manifest.json"
    if manifest_path.absolute() != expected_manifest_path.absolute() or _path_uses_symlink(
        root=root, path=manifest_path
    ):
        raise RecoveryAttemptRefused("recovery_budget_identity_mismatch")
    load_recovery_candidate_state(
        manifest=manifest,
        root=root,
        candidate_state_path=candidate_state_path,
        provider_parity_report_path=provider_parity_report_path,
        checked_at=reserved_at,
    )
    if run_id in {item.run_id for item in PLAN10_TERMINAL_RUNS} or selection_id == PLAN10_FORBIDDEN_SELECTION_ID:
        raise RecoveryAttemptRefused("plan10_identity_reuse_forbidden")
    if not _valid_sha256(prerequisite_state_sha256):
        raise RecoveryAttemptRefused("prerequisite_state_hash_invalid")

    manifest_sha256 = _sha256_bytes(manifest_payload)
    attempts_root = manifest_path.parent / "attempts"
    if _path_uses_symlink(root=root, path=attempts_root):
        raise RecoveryAttemptRefused("recovery_reservation_invalid")
    try:
        paths = sorted(attempts_root.glob("*.json")) if attempts_root.exists() else []
    except OSError:
        raise RecoveryAttemptRefused("recovery_reservation_invalid") from None
    expected_names = [f"{ordinal:02d}.json" for ordinal in range(1, len(paths) + 1)]
    if [path.name for path in paths] != expected_names or len(paths) > manifest.max_attempts:
        raise RecoveryAttemptRefused("recovery_reservation_invalid")
    reservations: list[ABRecoveryAttemptReservationV1] = []
    for path in paths:
        try:
            reservations.append(
                load_recovery_attempt_reservation(
                    path,
                    manifest=manifest,
                    manifest_sha256=manifest_sha256,
                )
            )
        except ValueError:
            raise RecoveryAttemptRefused("recovery_reservation_invalid") from None
    if len(reservations) >= manifest.max_attempts:
        raise RecoveryAttemptRefused("recovery_budget_exhausted")
    if any(item.run_id == run_id or item.selection_id == selection_id for item in reservations):
        raise RecoveryAttemptRefused("recovery_identity_reuse_forbidden")

    ordinal = len(reservations) + 1
    if ordinal == 1:
        authority_reason = "initial_attempt_allowed"
    else:
        authority = evaluate_recovery_retry_authority(
            manifest=manifest,
            previous_reservation=reservations[0],
            root=root,
            next_prerequisite_state_sha256=prerequisite_state_sha256,
        )
        if not authority.allowed:
            raise RecoveryAttemptRefused(authority.reason_code)
        authority_reason = authority.reason_code
    base: dict[str, Any] = {
        "schema_version": RECOVERY_ATTEMPT_SCHEMA_VERSION,
        "budget_id": manifest.budget_id,
        "budget_manifest_sha256": manifest_sha256,
        "ordinal": ordinal,
        "reserved_at": reserved_at,
        "run_id": run_id,
        "selection_id": selection_id,
        "candidate_state_sha256": manifest.candidate_state_sha256,
        "prerequisite_state_sha256": prerequisite_state_sha256,
        "authority_reason_code": authority_reason,
    }
    reservation = ABRecoveryAttemptReservationV1(
        **base,
        reservation_payload_sha256=_sha256_payload(
            ABRecoveryAttemptReservationV1.model_construct(
                **base,
                reservation_payload_sha256="sha256:" + "0" * 64,
            ).model_dump(mode="json", exclude={"reservation_payload_sha256"})
        ),
    )
    try:
        _write_create_only_bytes(
            attempts_root / f"{ordinal:02d}.json",
            canonical_report_json_bytes(reservation.model_dump(mode="json")),
        )
    except ValueError as error:
        raise RecoveryAttemptRefused("recovery_reservation_conflict") from error
    return reservation


def reserve_then_create_provider(
    *,
    reserve: Callable[[], ABRecoveryAttemptReservationV1],
    require_current_authority: Callable[[], None],
    provider_factory: Callable[[], _ProviderT],
) -> tuple[ABRecoveryAttemptReservationV1, _ProviderT]:
    """Make the reservation a forcing function before provider construction."""

    reservation = reserve()
    require_current_authority()
    return reservation, provider_factory()


def _recovery_authority(
    allowed: bool,
    reason_code: RecoveryAuthorityReason,
    previous_outcome: Literal["selected_pass", "candidate_failed", "unavailable", "execution_error"] | None,
) -> ABRecoveryRetryAuthorityV1:
    return ABRecoveryRetryAuthorityV1(
        allowed=allowed,
        reason_code=reason_code,
        previous_outcome=previous_outcome,
    )


def _recovery_report_matches_manifest(
    report: TerminalABRunV1,
    *,
    manifest: ABRecoveryBudgetManifestV1,
    expected_run_id: UUID,
) -> bool:
    return (
        report.run_id == expected_run_id
        and report.runtime.execution_kind == "full_provider"
        and report.runtime.tenant_id == manifest.tenant_id
        and report.runtime.incumbent.corpus_version_id == manifest.incumbent_corpus_version_id
        and report.runtime.candidate.corpus_version_id == manifest.candidate_corpus_version_id
        and report.parity.run_id == manifest.provider_parity_run_id
        and report.parity.report_sha256 == manifest.provider_parity_report_sha256
        and report.parity.config_fingerprint == manifest.provider_parity_config_fingerprint
        and report.parity.probe_fixture_sha256 == manifest.provider_parity_probe_fixture_sha256
        and report.parity.submitted_content_sha256 == manifest.provider_parity_submitted_content_sha256
        and report.inputs.manifest_hash == manifest.manifest_hash
        and report.inputs.gold_hash == manifest.gold_hash
        and report.inputs.dataset_baseline_identity == manifest.dataset_baseline_identity
    )


def _recovery_unavailable_has_sidecar(*, root: Path, run_id: UUID) -> bool:
    return any(
        path.exists()
        for path in (
            root / "diagnostics" / f"{run_id}.json",
            root / "diagnostics" / f"{run_id}.md",
            root / "commits" / str(run_id),
        )
    )


def build_candidate_observation_from_retrieval(
    *,
    role: Literal["incumbent", "candidate"],
    corpus_version_id: UUID,
    config_schema_version: str,
    config_fingerprint: str,
    deterministic_rebuild_sha256: str,
    rounds: tuple[Any, ...],
    retrieval_duration_ms: Decimal,
    cost_basis_version: str,
    cost_currency: Literal["CNY", "USD"],
    cost_unit_tokens: int,
    cost_price_per_unit: Decimal,
) -> ABCandidateObservationV1:
    """Convert one raw retrieval run to exact selection observations."""

    tagged_cases = tuple((round_result.round_format, case) for round_result in rounds for case in round_result.cases)
    cases = tuple(case for _, case in tagged_cases)
    ingestions = tuple(item for round_result in rounds for item in round_result.ingestions)
    answerable = tuple(case for case in cases if case.category != "no_answer")
    if len(cases) != SEALED_TOTAL_CASE_COUNT or len(answerable) != SEALED_ANSWERABLE_CASE_COUNT:
        raise ValueError("ab_case_count_mismatch")
    if len(rounds) != len(_FORMAT_ORDER) or tuple(item.round_format for item in rounds) != _FORMAT_ORDER:
        raise ValueError("ab_round_order_mismatch")
    if any(item.status != "success" for item in ingestions):
        raise ValueError("ab_ingestion_incomplete")
    fingerprints = {item.config_fingerprint for item in ingestions}
    if fingerprints != {config_fingerprint}:
        raise ValueError("ab_ingestion_config_mismatch")

    chunk_count = sum(item.chunk_count for item in ingestions)
    duplicate_count = sum(item.duplicate_count for item in ingestions)
    offline_tokens = sum(item.offline_embedding_tokens for item in ingestions)
    if chunk_count <= 0 or offline_tokens <= 0:
        raise ValueError("ab_resource_observation_missing")
    provider_reported = all(item.provider_tokens_status == "provider_reported" for item in ingestions)
    provider_tokens = (
        sum(int(item.provider_embedding_tokens or 0) for item in ingestions) if provider_reported else None
    )
    estimated_cost = Decimal(offline_tokens) * cost_price_per_unit / Decimal(cost_unit_tokens)
    return ABCandidateObservationV1(
        role=role,
        assembler="CharacterCompatibilityAssembler" if role == "incumbent" else "PolicyEmbeddingInputAssembler",
        config_schema_version=config_schema_version,
        config_fingerprint=config_fingerprint,
        corpus_version_id=corpus_version_id,
        deterministic_rebuild_sha256=deterministic_rebuild_sha256,
        quality=_quality_from_cases(tagged_cases),
        resources=ABResourceMetricsV1(
            chunk_count=chunk_count,
            duplicate_count=duplicate_count,
            offline_embedding_tokens=offline_tokens,
            provider_embedding_tokens=provider_tokens,
            provider_tokens_status="provider_reported" if provider_reported else "unavailable",
            retrieval_duration_ms=retrieval_duration_ms,
            embedding_cost=ABEmbeddingCostV1(
                basis_version=cost_basis_version,
                currency=cost_currency,
                unit_tokens=cost_unit_tokens,
                price_per_unit=cost_price_per_unit,
                estimated_cost=estimated_cost,
                observed_cost=None,
                observed_cost_status="unavailable",
            ),
        ),
    )


def _quality_from_cases(tagged_cases: tuple[tuple[str, Any], ...]) -> ABQualityMetricsV1:
    cases = tuple(case for _, case in tagged_cases)
    answerable = tuple(case for case in cases if case.category != "no_answer")
    by_format: list[ABFormatMetricsV1] = []
    for format_name in _FORMAT_ORDER:
        format_cases = tuple(
            case for case_format, case in tagged_cases if case_format == format_name and case.category != "no_answer"
        )
        if len(format_cases) != SEALED_ANSWERABLE_CASE_COUNT // len(_FORMAT_ORDER):
            raise ValueError("ab_format_case_count_mismatch")
        by_format.append(
            ABFormatMetricsV1(
                format=format_name,  # type: ignore[arg-type]
                hit_at_1=_boolean_ratio(format_cases, "hit_at_1"),
                hit_at_3=_boolean_ratio(format_cases, "hit_at_3"),
                hit_at_5=_boolean_ratio(format_cases, "hit_at_5"),
                mrr=_mrr_ratio(format_cases),
            )
        )
    anchor_denominator = sum(int(case.semantic_anchor_total) for case in answerable)
    locator_cases = tuple(case for case in answerable if case.locator_expected)
    fallback_successes = sum(
        bool(case.no_answer_correct) if case.category == "no_answer" else case.service_status != "no_evidence"
        for case in cases
    )
    return ABQualityMetricsV1(
        answerable_case_count=SEALED_ANSWERABLE_CASE_COUNT,
        total_case_count=SEALED_TOTAL_CASE_COUNT,
        hit_at_1=_boolean_ratio(answerable, "hit_at_1"),
        hit_at_3=_boolean_ratio(answerable, "hit_at_3"),
        hit_at_5=_boolean_ratio(answerable, "hit_at_5"),
        mrr=_mrr_ratio(answerable),
        semantic_anchor_coverage=ExactRatioV1(
            numerator=sum(int(case.semantic_anchor_hits) for case in answerable),
            denominator=anchor_denominator,
        ),
        locator_coverage=ExactRatioV1(
            numerator=sum(bool(case.locator_covered) for case in locator_cases),
            denominator=len(locator_cases),
        ),
        fallback_correctness=ExactRatioV1(
            numerator=fallback_successes,
            denominator=len(cases),
        ),
        by_format=tuple(by_format),
    )


def _boolean_ratio(cases: tuple[Any, ...], attribute: str) -> ExactRatioV1:
    return ExactRatioV1(
        numerator=sum(bool(getattr(case, attribute)) for case in cases),
        denominator=len(cases),
    )


def _mrr_ratio(cases: tuple[Any, ...]) -> ExactRatioV1:
    total = Fraction(0)
    for case in cases:
        try:
            rank = tuple(case.ranked_doc_keys).index(case.policy_id) + 1
        except ValueError:
            continue
        total += Fraction(1, rank)
    return ExactRatioV1.from_fraction(total / len(cases))


def evaluate_exact_gates(
    *,
    incumbent: ABCandidateObservationV1,
    candidate: ABCandidateObservationV1,
) -> tuple[ABGateObservationV1, ...]:
    """Apply the fixed profile using exact rational comparisons only."""

    if incumbent.role != "incumbent" or candidate.role != "candidate":
        raise ValueError("candidate_role_mismatch")
    rows: list[ABGateObservationV1] = []

    def append(
        gate: GateName,
        operator: Literal[">=", "<="],
        candidate_value: Fraction,
        incumbent_value: Fraction | None,
        limit: Fraction,
    ) -> None:
        rows.append(
            ABGateObservationV1(
                gate=gate,
                operator=operator,
                candidate=ExactRatioV1.from_fraction(candidate_value),
                incumbent=(None if incumbent_value is None else ExactRatioV1.from_fraction(incumbent_value)),
                limit=ExactRatioV1.from_fraction(limit),
                passed=candidate_value >= limit if operator == ">=" else candidate_value <= limit,
            )
        )

    incumbent_quality = incumbent.quality
    candidate_quality = candidate.quality
    append(
        "hit_at_5",
        ">=",
        candidate_quality.hit_at_5.fraction,
        incumbent_quality.hit_at_5.fraction,
        max(Fraction(9, 10), incumbent_quality.hit_at_5.fraction),
    )
    append(
        "cross_format_hit_at_5_spread",
        "<=",
        candidate_quality.hit_at_5_spread.fraction,
        incumbent_quality.hit_at_5_spread.fraction,
        min(Fraction(1, 10), incumbent_quality.hit_at_5_spread.fraction),
    )
    for gate, attribute in (
        ("hit_at_1_non_regression", "hit_at_1"),
        ("hit_at_3_non_regression", "hit_at_3"),
        ("mrr_non_regression", "mrr"),
    ):
        incumbent_value = getattr(incumbent_quality, attribute).fraction
        append(
            gate,
            ">=",
            getattr(candidate_quality, attribute).fraction,
            incumbent_value,
            max(Fraction(0), incumbent_value - Fraction(1, 45)),
        )
    for incumbent_format, candidate_format in zip(
        incumbent_quality.by_format, candidate_quality.by_format, strict=True
    ):
        incumbent_value = incumbent_format.hit_at_5.fraction
        append(
            f"format_hit_at_5_{incumbent_format.format}",  # type: ignore[arg-type]
            ">=",
            candidate_format.hit_at_5.fraction,
            incumbent_value,
            max(Fraction(0), incumbent_value - Fraction(1, 15)),
        )
    for gate, attribute in (
        ("semantic_anchor_non_regression", "semantic_anchor_coverage"),
        ("locator_non_regression", "locator_coverage"),
        ("fallback_non_regression", "fallback_correctness"),
    ):
        incumbent_value = getattr(incumbent_quality, attribute).fraction
        append(
            gate,
            ">=",
            getattr(candidate_quality, attribute).fraction,
            incumbent_value,
            max(Fraction(0), incumbent_value - Fraction(1, 54)),
        )
    append(
        "duplicate_rate",
        "<=",
        candidate.resources.duplicate_rate.fraction,
        incumbent.resources.duplicate_rate.fraction,
        incumbent.resources.duplicate_rate.fraction + Fraction(1, 50),
    )
    append(
        "chunk_count_ratio",
        "<=",
        Fraction(candidate.resources.chunk_count, incumbent.resources.chunk_count),
        Fraction(1),
        Fraction(3, 2),
    )
    append(
        "embedding_token_ratio",
        "<=",
        Fraction(
            candidate.resources.offline_embedding_tokens,
            incumbent.resources.offline_embedding_tokens,
        ),
        Fraction(1),
        Fraction(5, 4),
    )
    return tuple(rows)


def build_terminal_ab_run(
    *,
    run_id: UUID,
    generated_at: datetime,
    inputs: ABInputIdentityV1,
    runtime: ABRuntimeConfigV1,
    parity: ABParityEvidenceV1,
    incumbent: ABCandidateObservationV1,
    candidate: ABCandidateObservationV1,
    hard_proofs: ABHardProofsV1,
) -> TerminalABRunV1:
    if parity.status != "passed":
        return TerminalABRunV1(
            run_id=run_id,
            generated_at=generated_at,
            outcome="unavailable",
            failure_class=None,
            terminal_stage="parity",
            safe_reason_codes=(parity.reason_code,),
            inputs=inputs,
            runtime=runtime,
            parity=parity,
            incumbent=None,
            candidate=None,
            hard_proofs=None,
            gates=(),
        )
    gates = evaluate_exact_gates(incumbent=incumbent, candidate=candidate)
    if not hard_proofs.all_passed:
        outcome = "candidate_failed"
        failure_class = "safety_fail"
        terminal_stage = "safety"
        reasons = ("hard_safety_gate_failed",)
    elif any(not gate.passed for gate in gates):
        outcome = "candidate_failed"
        failure_class = "quality_fail"
        terminal_stage = "quality"
        reasons = ("quality_gate_failed",)
    else:
        outcome = "selected_pass"
        failure_class = None
        terminal_stage = "selection"
        reasons = ()
    return TerminalABRunV1(
        run_id=run_id,
        generated_at=generated_at,
        outcome=outcome,
        failure_class=failure_class,
        terminal_stage=terminal_stage,
        safe_reason_codes=reasons,
        inputs=inputs,
        runtime=runtime,
        parity=parity,
        incumbent=incumbent,
        candidate=candidate,
        hard_proofs=hard_proofs,
        gates=gates,
    )


def render_terminal_markdown(payload: Mapping[str, Any]) -> str:
    report = TerminalABRunV1.model_validate(payload)
    lines = [
        "# RAG Token Chunk A-B Run",
        "",
        f"Schema: `{report.schema_version}`",
        f"Run: `{report.run_id}`",
        f"Outcome: `{report.outcome}`",
        f"Failure class: `{report.failure_class or 'none'}`",
        f"Terminal stage: `{report.terminal_stage}`",
        "",
        "## Sealed inputs",
        "",
        f"- Manifest SHA-256: `{report.inputs.manifest_hash}`",
        f"- Gold SHA-256: `{report.inputs.gold_hash}`",
        f"- Dataset baseline identity: `{report.inputs.dataset_baseline_identity}`",
        f"- Cases: answerable={report.inputs.answerable_case_count}; total={report.inputs.total_case_count}",
        f"- Provider parity report SHA-256: `{report.parity.report_sha256}`",
        "",
        "## Exact gates",
        "",
        "| Gate | Candidate | Incumbent | Operator | Exact limit | Status |",
        "| --- | ---: | ---: | --- | ---: | --- |",
    ]
    if not report.gates:
        lines.append("| not evaluated | n/a | n/a | n/a | n/a | NOT_EVALUATED |")
    for gate in report.gates:
        incumbent = "n/a" if gate.incumbent is None else _ratio_display(gate.incumbent)
        lines.append(
            f"| {gate.gate} | {_ratio_display(gate.candidate)} | {incumbent} | "
            f"{gate.operator} | {_ratio_display(gate.limit)} | {'PASS' if gate.passed else 'FAIL'} |"
        )
    lines.extend(["", "## Safe terminal reasons", ""])
    lines.append(", ".join(report.safe_reason_codes) if report.safe_reason_codes else "none")
    return "\n".join(lines) + "\n"


def render_selection_markdown(payload: Mapping[str, Any]) -> str:
    decision = ABSelectionDecisionV1.model_validate(payload)
    return "\n".join(
        (
            "# RAG Token Chunk Selection",
            "",
            f"Schema: `{decision.schema_version}`",
            f"Selection: `{decision.selection_id}`",
            f"Outcome: `{decision.outcome}`",
            f"Terminal run: `{decision.terminal_run_id}`",
            f"Terminal run SHA-256: `{decision.terminal_run_sha256}`",
            f"Provider parity report SHA-256: `{decision.provider_parity_report_sha256}`",
            f"Candidate corpus: `{decision.candidate_corpus_version_id}`",
            f"Candidate config observation SHA-256: `{decision.candidate_observation_sha256}`",
            f"Exact gate profile SHA-256: `{decision.exact_gate_profile_sha256}`",
            f"Decision payload SHA-256: `{decision.decision_payload_sha256}`",
            "",
        )
    )


def render_execution_diagnostic_markdown(payload: Mapping[str, Any]) -> str:
    diagnostic = ABExecutionDiagnosticV1.model_validate(payload)
    return "\n".join(
        (
            "# RAG Token Chunk Execution Diagnostic",
            "",
            f"Schema: `{diagnostic.schema_version}`",
            f"Run: `{diagnostic.run_id}`",
            f"Terminal run SHA-256: `{diagnostic.terminal_run_sha256}`",
            f"Failing role: `{diagnostic.failing_role}`",
            f"Round: `{diagnostic.round_format or 'none'}`",
            f"Stage: `{diagnostic.stage}`",
            f"Reason: `{diagnostic.reason_code}`",
            f"Provider availability: `{diagnostic.provider_availability}`",
            f"Provider request: `{diagnostic.provider_request_classification}`",
            f"Outer rollback attempted: `{'true' if diagnostic.outer_rollback_attempted else 'false'}`",
            f"Outer rollback proved: `{'true' if diagnostic.outer_rollback_proved else 'false'}`",
            f"Completed rounds: `{diagnostic.completed_round_count}`",
            f"Provider requests: `{diagnostic.provider_request_count}`",
            f"Safe context SHA-256: `{diagnostic.safe_context_sha256 or 'none'}`",
            "",
        )
    )


def write_terminal_run_create_only(report: TerminalABRunV1, *, root: Path) -> ImmutableArtifactPairV1:
    validated = TerminalABRunV1.model_validate(report.model_dump(mode="json"))
    return _write_create_only_pair(
        json_path=root / "runs" / f"{validated.run_id}.json",
        markdown_path=root / "runs" / f"{validated.run_id}.md",
        json_payload=canonical_report_json_bytes(validated.model_dump(mode="json")),
        markdown_payload=render_terminal_markdown(validated.model_dump(mode="json")).encode(),
    )


def load_terminal_ab_run(path: Path) -> TerminalABRunV1:
    try:
        payload = json.loads(path.read_bytes())
    except (OSError, TypeError, ValueError):
        raise ValueError("terminal_report_invalid") from None
    try:
        return TerminalABRunV1.model_validate(payload)
    except ValidationError:
        raise


def write_execution_error_bundle_create_only(
    report: TerminalABRunV1,
    *,
    diagnostic: ABExecutionDiagnosticV1,
    root: Path,
    fault_injector: ExecutionBundleFaultInjector | None = None,
) -> ImmutableExecutionBundleV1:
    """Crash-consistently publish one immutable execution-error evidence bundle.

    The four legacy/diagnostic files may exist before commit, but readers ignore
    them until the create-only commit directory is atomically renamed into
    place. A retry accepts only the exact canonical bytes from the first try.
    """

    validated_report = TerminalABRunV1.model_validate(report.model_dump(mode="json"))
    validated_diagnostic = ABExecutionDiagnosticV1.model_validate(diagnostic.model_dump(mode="json"))
    if validated_report.outcome != "execution_error":
        raise ValueError("execution_error_required")
    if validated_diagnostic.run_id != validated_report.run_id:
        raise ValueError("bundle_identity_mismatch")

    run_json = canonical_report_json_bytes(validated_report.model_dump(mode="json"))
    run_markdown = render_terminal_markdown(validated_report.model_dump(mode="json")).encode()
    run_sha256 = _sha256_bytes(run_json)
    if validated_diagnostic.terminal_run_sha256 != run_sha256:
        raise ValueError("terminal_run_hash_mismatch")
    diagnostic_json = canonical_report_json_bytes(validated_diagnostic.model_dump(mode="json"))
    diagnostic_markdown = render_execution_diagnostic_markdown(validated_diagnostic.model_dump(mode="json")).encode()

    run_id = str(validated_report.run_id)
    staged_root = root / ".staging" / run_id
    staged_payloads = {
        "run_json": (staged_root / "run.json", run_json),
        "run_markdown": (staged_root / "run.md", run_markdown),
        "diagnostic_json": (staged_root / "diagnostic.json", diagnostic_json),
        "diagnostic_markdown": (staged_root / "diagnostic.md", diagnostic_markdown),
    }
    try:
        staged_root.mkdir(parents=True, exist_ok=True)
    except OSError:
        raise ValueError("write_failed") from None
    _fsync_directory(staged_root.parent)
    _inject_fault(fault_injector, "staging_parent_fsync")
    _fsync_directory(root)
    _inject_fault(fault_injector, "output_root_fsync:staging")
    for name, (path, payload) in staged_payloads.items():
        _stage_bundle_payload(
            path,
            payload,
            write_boundary=f"stage_write:{name}",
            fsync_boundary=f"stage_fsync:{name}",
            fault_injector=fault_injector,
        )
    _fsync_directory(staged_root)
    _inject_fault(fault_injector, "stage_dir_fsync")

    final_payloads = {
        "run_json": (root / "runs" / f"{run_id}.json", run_json),
        "run_markdown": (root / "runs" / f"{run_id}.md", run_markdown),
        "diagnostic_json": (root / "diagnostics" / f"{run_id}.json", diagnostic_json),
        "diagnostic_markdown": (root / "diagnostics" / f"{run_id}.md", diagnostic_markdown),
    }
    for name, (target, payload) in final_payloads.items():
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
        except OSError:
            raise ValueError("write_failed") from None
        _fsync_directory(root)
        _inject_fault(fault_injector, f"publish_parent_fsync:{name}")
        _publish_bundle_link(
            source=staged_payloads[name][0],
            target=target,
            payload=payload,
        )
        _inject_fault(fault_injector, f"publish_link:{name}")
        _fsync_directory(target.parent)
        _inject_fault(fault_injector, f"publish_fsync:{name}")

    manifest = ABExecutionBundleManifestV1(
        run_id=validated_report.run_id,
        terminal_run_sha256=run_sha256,
        run_markdown_sha256=_sha256_bytes(run_markdown),
        diagnostic_json_sha256=_sha256_bytes(diagnostic_json),
        diagnostic_markdown_sha256=_sha256_bytes(diagnostic_markdown),
    )
    manifest_payload = canonical_report_json_bytes(manifest.model_dump(mode="json"))
    commit_stage_dir = staged_root / "commit"
    try:
        commit_stage_dir.mkdir(exist_ok=True)
    except OSError:
        raise ValueError("write_failed") from None
    _fsync_directory(staged_root)
    _inject_fault(fault_injector, "manifest_source_parent_fsync")
    _stage_bundle_payload(
        commit_stage_dir / "manifest.json",
        manifest_payload,
        write_boundary="manifest_stage_write",
        fsync_boundary="manifest_stage_fsync",
        fault_injector=fault_injector,
    )
    _fsync_directory(commit_stage_dir)
    _inject_fault(fault_injector, "manifest_dir_fsync")

    commits_root = root / "commits"
    final_commit_dir = commits_root / run_id
    try:
        commits_root.mkdir(parents=True, exist_ok=True)
    except OSError:
        raise ValueError("write_failed") from None
    _fsync_directory(root)
    _inject_fault(fault_injector, "commits_parent_fsync")
    final_manifest_path = final_commit_dir / "manifest.json"
    if final_commit_dir.exists():
        if not final_commit_dir.is_dir() or _read_bytes_or_conflict(final_manifest_path) != manifest_payload:
            raise ValueError("bundle_conflict")
    else:
        _inject_fault(fault_injector, "manifest_rename")
        try:
            os.rename(commit_stage_dir, final_commit_dir)
        except OSError:
            if not final_commit_dir.is_dir() or _read_bytes_or_conflict(final_manifest_path) != manifest_payload:
                raise ValueError("bundle_conflict") from None
    _fsync_directory(commits_root)
    _inject_fault(fault_injector, "manifest_parent_fsync")
    _fsync_directory(staged_root)
    _inject_fault(fault_injector, "manifest_source_parent_post_rename_fsync")
    loaded = load_execution_error_bundle(root=root, run_id=validated_report.run_id)
    if loaded.manifest != manifest:
        raise ValueError("bundle_conflict")
    return ImmutableExecutionBundleV1(
        manifest=manifest,
        manifest_path=final_manifest_path,
        run=ImmutableArtifactPairV1(
            json_path=final_payloads["run_json"][0],
            markdown_path=final_payloads["run_markdown"][0],
            json_sha256=manifest.terminal_run_sha256,
            markdown_sha256=manifest.run_markdown_sha256,
        ),
        diagnostic=ImmutableArtifactPairV1(
            json_path=final_payloads["diagnostic_json"][0],
            markdown_path=final_payloads["diagnostic_markdown"][0],
            json_sha256=manifest.diagnostic_json_sha256,
            markdown_sha256=manifest.diagnostic_markdown_sha256,
        ),
    )


def load_execution_error_bundle(*, root: Path, run_id: UUID) -> LoadedExecutionBundleV1:
    """Load only a hash-valid, manifest-committed four-file bundle."""

    manifest_path = root / "commits" / str(run_id) / "manifest.json"
    if not manifest_path.is_file():
        raise ValueError("bundle_uncommitted")
    try:
        manifest = ABExecutionBundleManifestV1.model_validate_json(manifest_path.read_bytes())
    except (OSError, ValidationError, ValueError):
        raise ValueError("bundle_invalid") from None
    if manifest.run_id != run_id:
        raise ValueError("bundle_invalid")
    paths = {
        "run_json": root / "runs" / f"{run_id}.json",
        "run_markdown": root / "runs" / f"{run_id}.md",
        "diagnostic_json": root / "diagnostics" / f"{run_id}.json",
        "diagnostic_markdown": root / "diagnostics" / f"{run_id}.md",
    }
    try:
        payloads = {name: path.read_bytes() for name, path in paths.items()}
    except OSError:
        raise ValueError("bundle_invalid") from None
    expected_hashes = {
        "run_json": manifest.terminal_run_sha256,
        "run_markdown": manifest.run_markdown_sha256,
        "diagnostic_json": manifest.diagnostic_json_sha256,
        "diagnostic_markdown": manifest.diagnostic_markdown_sha256,
    }
    if any(_sha256_bytes(payloads[name]) != digest for name, digest in expected_hashes.items()):
        raise ValueError("bundle_invalid")
    try:
        report = TerminalABRunV1.model_validate_json(payloads["run_json"])
        diagnostic = ABExecutionDiagnosticV1.model_validate_json(payloads["diagnostic_json"])
    except (ValidationError, ValueError):
        raise ValueError("bundle_invalid") from None
    if (
        report.outcome != "execution_error"
        or report.run_id != run_id
        or diagnostic.run_id != run_id
        or diagnostic.terminal_run_sha256 != manifest.terminal_run_sha256
        or payloads["run_markdown"] != render_terminal_markdown(report.model_dump(mode="json")).encode()
        or payloads["diagnostic_markdown"]
        != render_execution_diagnostic_markdown(diagnostic.model_dump(mode="json")).encode()
    ):
        raise ValueError("bundle_invalid")
    return LoadedExecutionBundleV1(
        manifest=manifest,
        report=report,
        diagnostic=diagnostic,
    )


def write_selection_create_only(
    report: TerminalABRunV1,
    *,
    binding: ABSelectionBindingV1,
    terminal_run_sha256: str,
    root: Path,
) -> ImmutableArtifactPairV1:
    if report.outcome != "selected_pass":
        raise ValueError("selected_pass_required")
    validated = TerminalABRunV1.model_validate(report.model_dump(mode="json"))
    if binding.tenant_id != validated.runtime.tenant_id:
        raise ValueError("selection_binding_mismatch")
    if validated.candidate is None or binding.candidate_corpus_version_id != validated.candidate.corpus_version_id:
        raise ValueError("selection_binding_mismatch")
    if not _valid_sha256(terminal_run_sha256):
        raise ValueError("terminal_run_hash_invalid")
    base: dict[str, Any] = {
        "schema_version": SELECTION_SCHEMA_VERSION,
        "selection_id": binding.selection_id,
        "selected_at": validated.generated_at,
        "outcome": "selected_pass",
        "terminal_run_id": validated.run_id,
        "terminal_run_sha256": terminal_run_sha256,
        "provider_parity_report_sha256": validated.parity.report_sha256,
        "tenant_id": binding.tenant_id,
        "candidate_corpus_version_id": binding.candidate_corpus_version_id,
        "candidate_run_token": binding.candidate_run_token,
        "candidate_lease_owner": binding.candidate_lease_owner,
        "source_manifest_hash": binding.source_manifest_hash,
        "manifest_hash": validated.inputs.manifest_hash,
        "gold_hash": validated.inputs.gold_hash,
        "dataset_baseline_identity": validated.inputs.dataset_baseline_identity,
        "runtime_config_sha256": _sha256_payload(validated.runtime.model_dump(mode="json")),
        "candidate_observation_sha256": _sha256_payload(validated.candidate.model_dump(mode="json")),
        "exact_gate_profile_sha256": _sha256_payload([gate.model_dump(mode="json") for gate in validated.gates]),
    }
    unsealed = ABSelectionDecisionV1.model_construct(
        **base,
        decision_payload_sha256="sha256:" + "0" * 64,
    )
    decision = ABSelectionDecisionV1(
        **base,
        decision_payload_sha256=_sha256_payload(unsealed.model_dump(mode="json", exclude={"decision_payload_sha256"})),
    )
    return _write_create_only_pair(
        json_path=root / "selections" / f"{binding.selection_id}.json",
        markdown_path=root / "selections" / f"{binding.selection_id}.md",
        json_payload=canonical_report_json_bytes(decision.model_dump(mode="json")),
        markdown_payload=render_selection_markdown(decision.model_dump(mode="json")).encode(),
    )


def load_selection_decision(path: Path) -> ABSelectionDecisionV1:
    try:
        payload = json.loads(path.read_bytes())
    except (OSError, TypeError, ValueError):
        raise ValueError("selection_decision_invalid") from None
    return ABSelectionDecisionV1.model_validate(payload)


def _ratio_display(value: ExactRatioV1) -> str:
    display = Decimal(value.numerator) / Decimal(value.denominator)
    return f"{value.numerator}/{value.denominator} ({display:.6f})"


def _sha256_payload(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _valid_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and value.startswith("sha256:")
        and len(value) == 71
        and all(character in "0123456789abcdef" for character in value[7:])
    )


def _write_create_only_pair(
    *,
    json_path: Path,
    markdown_path: Path,
    json_payload: bytes,
    markdown_payload: bytes,
) -> ImmutableArtifactPairV1:
    try:
        json_path.parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        raise ValueError("write_failed") from None
    if json_path.exists() or markdown_path.exists():
        raise ValueError("create_conflict")
    temporary_paths: list[Path] = []
    linked: list[Path] = []
    try:
        for target, payload in ((json_path, json_payload), (markdown_path, markdown_payload)):
            descriptor, temporary_name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=target.parent)
            temporary = Path(temporary_name)
            temporary_paths.append(temporary)
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.link(temporary, target)
            linked.append(target)
    except FileExistsError:
        for target in linked:
            target.unlink(missing_ok=True)
        raise ValueError("create_conflict") from None
    except OSError:
        for target in linked:
            target.unlink(missing_ok=True)
        raise ValueError("write_failed") from None
    finally:
        for temporary in temporary_paths:
            temporary.unlink(missing_ok=True)
    return ImmutableArtifactPairV1(
        json_path=json_path,
        markdown_path=markdown_path,
        json_sha256=_sha256_bytes(json_payload),
        markdown_sha256=_sha256_bytes(markdown_payload),
    )


def _write_create_only_bytes(path: Path, payload: bytes) -> None:
    """Publish one fsynced file with a create-only hard-link commit point."""

    temporary: Path | None = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
        temporary = Path(temporary_name)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, path)
        _fsync_directory(path.parent)
    except FileExistsError:
        raise ValueError("create_conflict") from None
    except OSError:
        raise ValueError("write_failed") from None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _stage_bundle_payload(
    path: Path,
    payload: bytes,
    *,
    write_boundary: str,
    fsync_boundary: str,
    fault_injector: ExecutionBundleFaultInjector | None,
) -> None:
    try:
        if path.exists():
            with path.open("rb") as stream:
                if stream.read() != payload:
                    raise ValueError("bundle_conflict")
                os.fsync(stream.fileno())
        else:
            with path.open("xb") as stream:
                stream.write(payload)
                stream.flush()
                _inject_fault(fault_injector, write_boundary)
                os.fsync(stream.fileno())
        _inject_fault(fault_injector, fsync_boundary)
    except ValueError:
        raise
    except OSError:
        raise ValueError("write_failed") from None


def _publish_bundle_link(*, source: Path, target: Path, payload: bytes) -> None:
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            if _read_bytes_or_conflict(target) != payload:
                raise ValueError("bundle_conflict")
            return
        os.link(source, target)
    except FileExistsError:
        if _read_bytes_or_conflict(target) != payload:
            raise ValueError("bundle_conflict") from None
    except ValueError:
        raise
    except OSError:
        raise ValueError("write_failed") from None


def _read_bytes_or_conflict(path: Path) -> bytes:
    try:
        return path.read_bytes()
    except OSError:
        raise ValueError("bundle_conflict") from None


def _fsync_directory(path: Path) -> None:
    try:
        descriptor = os.open(path, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    except OSError:
        raise ValueError("write_failed") from None


def _inject_fault(fault_injector: ExecutionBundleFaultInjector | None, boundary: str) -> None:
    if fault_injector is not None:
        fault_injector(boundary)


def _sha256_bytes(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()
