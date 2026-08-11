"""Provider-backed, evaluation-owned retrieval format-parity orchestration."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal
from uuid import NAMESPACE_URL, UUID, uuid5

from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy.ext.asyncio import AsyncSession

from src.knowledge.config import RERANK_CONFIG_VERSION, RETRIEVAL_CONFIG_VERSION
from src.knowledge.retrieval import PolicyRetrievalEngine, PolicyRetrievalRun
from src.knowledge.provenance import EvidenceProvenance
from src.knowledge.text_hash import evidence_text_hash
from src.knowledge.schemas import (
    KnowledgeContext,
    KnowledgeSearchFilters,
    KnowledgeSearchRequest,
)
from src.knowledge.service import PolicyKnowledgeService
from src.rag.embedder import EmbeddingService
from src.rag.evaluation.contracts import EvaluationOutcome, FormatParityDataset, SemanticCase
from src.rag.ingestion import IngestionAssemblyMode, IngestionService, PolicyInputAssembler
from src.rag.policy_embedding_input import PolicyEmbeddingInputAssembler
from src.repositories.rag_evaluation_round_repo import (
    FORMAT_PARITY_OWNER_MARKER,
    FORMAT_PARITY_TENANT_ID,
    ROUND_FORMATS,
    AnchorLocatorRequirement,
    EvaluationIsolationError,
    EvaluationRoundIdentity,
    IngestionResourceProof,
    ProjectionState,
    RecordedChunkLocatorProof,
    RecordedSourceLocatorProof,
    RollbackBaselineProof,
    RagEvaluationRoundRepository,
    validate_run_sequence,
)


class PrerequisiteStatusV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(min_length=1, max_length=64)
    available: bool
    reason_code: str | None = Field(default=None, max_length=64)


class SafeRoleFailureV1(BaseModel):
    """Allowlisted runtime failure provenance with no raw exception surface."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    failing_role: Literal["character_incumbent", "token_candidate", "shared_preflight"]
    round_format: Literal["markdown", "digital_pdf", "scanned_pdf"] | None = None
    stage: Literal[
        "shared_preflight",
        "role_setup",
        "format_ingestion",
        "retrieval_resource_proof",
        "post_rollback_baseline_verification",
    ]
    reason_code: Literal[
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
    safe_context_sha256: str | None = Field(default=None, pattern=r"^sha256:[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_failure(self) -> SafeRoleFailureV1:
        expected_reasons = {
            "shared_preflight": {"candidate_state_invalid", "sealed_input_invalid", "candidate_pair_invalid"},
            "role_setup": {"role_setup_failed"},
            "format_ingestion": {"format_ingestion_failed", "provider_request_failed"},
            "retrieval_resource_proof": {
                "provider_request_failed",
                "resource_proof_failed",
                "provider_execution_failed",
            },
            "post_rollback_baseline_verification": {"rollback_proof_failed"},
        }
        if self.reason_code not in expected_reasons[self.stage]:
            raise ValueError("safe_failure_stage_reason_mismatch")
        if self.outer_rollback_proved and not self.outer_rollback_attempted:
            raise ValueError("safe_failure_rollback_mismatch")
        if self.provider_request_classification in {"request_started", "request_completed"}:
            if self.provider_availability != "available":
                raise ValueError("safe_failure_provider_mismatch")
        if self.provider_request_classification == "not_attempted" and self.provider_request_count:
            raise ValueError("safe_failure_request_count_mismatch")
        return self


class SafeRoleExecutionError(RuntimeError):
    """Generic external error carrying only a validated safe failure value."""

    def __init__(self, failure: SafeRoleFailureV1) -> None:
        self.failure = SafeRoleFailureV1.model_validate(failure.model_dump(mode="json"))
        super().__init__("role execution failed")


class IngestionObservationV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    doc_key: str
    source_checksum: str = Field(pattern=r"^[0-9a-f]{64}$")
    status: Literal["success", "failed"]
    error_code: str | None = None
    chunk_count: int = Field(default=0, ge=0)
    duplicate_count: int = Field(default=0, ge=0)
    offline_embedding_tokens: int = Field(default=0, ge=0)
    provider_embedding_tokens: int | None = Field(default=None, ge=0)
    provider_tokens_status: Literal["provider_reported", "unavailable"] = "unavailable"
    config_fingerprint: str | None = Field(default=None, pattern=r"^sha256:[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_resources(self) -> IngestionObservationV1:
        if self.duplicate_count > self.chunk_count:
            raise ValueError("ingestion_duplicate_count_invalid")
        if (self.provider_embedding_tokens is None) != (self.provider_tokens_status == "unavailable"):
            raise ValueError("ingestion_provider_token_status_mismatch")
        return self


class RetrievalCaseObservationV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    policy_id: str
    case_id: str
    question: str
    category: str
    service_status: str
    ranked_doc_keys: tuple[str, ...] = ()
    hit_at_1: bool
    hit_at_3: bool
    hit_at_5: bool
    reciprocal_rank: float = Field(ge=0.0, le=1.0)
    semantic_anchor_hits: int = Field(ge=0)
    semantic_anchor_total: int = Field(ge=0)
    no_answer_correct: bool
    locator_expected: bool
    locator_covered: bool
    query_rewrite: str | None = None
    fallback_reason: str | None = None
    rerank_observed: bool = False


class RetrievalRoundResultV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    round_format: Literal["markdown", "digital_pdf", "scanned_pdf"]
    round_token: str
    outcome: EvaluationOutcome
    ingestions: tuple[IngestionObservationV1, ...] = ()
    cases: tuple[RetrievalCaseObservationV1, ...] = ()
    pre_state_proved: bool = False
    exactly_three_current_proved: bool = False
    post_state_proved: bool = False
    immutable_history_preserved: bool = False
    reason_code: str | None = None
    safe_failure: SafeRoleFailureV1 | None = None


class RetrievalParityRunV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["retrieval_parity_run.v1"] = "retrieval_parity_run.v1"
    mode: Literal["provider", "contract_test"]
    baseline_eligible: bool
    outcome: EvaluationOutcome
    generated_at: str
    tenant_id: str
    owner_marker: str
    run_token: str
    manifest_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    gold_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    baseline_identity: str = Field(pattern=r"^[0-9a-f]{64}$")
    rounds: tuple[RetrievalRoundResultV1, ...]
    prerequisites: tuple[PrerequisiteStatusV1, ...]

    @model_validator(mode="after")
    def validate_baseline_eligibility(self) -> RetrievalParityRunV1:
        if self.mode == "contract_test" and self.baseline_eligible:
            raise ValueError("contract_test cannot be baseline eligible")
        if self.tenant_id != str(FORMAT_PARITY_TENANT_ID):
            raise ValueError("provider result must use fixed evaluation tenant")
        if self.owner_marker != FORMAT_PARITY_OWNER_MARKER:
            raise ValueError("provider result must use fixed owner marker")
        return self


@dataclass(frozen=True, slots=True)
class ABRoundNamespace:
    """One deterministic role/corpus owner inside an A/B evaluation run."""

    role: Literal["incumbent", "candidate"]
    corpus_version_id: UUID
    run_token: UUID
    round_owner: str
    evaluation_owner_marker: str = FORMAT_PARITY_OWNER_MARKER


def build_ab_round_namespaces(
    *,
    run_id: UUID,
    incumbent_corpus_version_id: UUID,
    candidate_corpus_version_id: UUID,
) -> tuple[ABRoundNamespace, ABRoundNamespace]:
    """Derive stable, non-overlapping role owners without changing DB ownership."""

    if (
        run_id.int == 0
        or incumbent_corpus_version_id.int == 0
        or candidate_corpus_version_id.int == 0
        or incumbent_corpus_version_id == candidate_corpus_version_id
    ):
        raise EvaluationIsolationError("ab_namespace_invalid")

    def namespace(role: Literal["incumbent", "candidate"], corpus_version_id: UUID) -> ABRoundNamespace:
        return ABRoundNamespace(
            role=role,
            corpus_version_id=corpus_version_id,
            run_token=uuid5(NAMESPACE_URL, f"{run_id}:rag-token-chunk-ab:{role}"),
            round_owner=f"moca.rag_token_chunk_ab.v1:{role}",
        )

    return (
        namespace("incumbent", incumbent_corpus_version_id),
        namespace("candidate", candidate_corpus_version_id),
    )


def _diagnostic_role(namespace: ABRoundNamespace) -> Literal["character_incumbent", "token_candidate"]:
    return "character_incumbent" if namespace.role == "incumbent" else "token_candidate"


def _safe_role_failure(
    *,
    role: Literal["character_incumbent", "token_candidate", "shared_preflight"],
    round_format: Literal["markdown", "digital_pdf", "scanned_pdf"] | None,
    stage: Literal[
        "shared_preflight",
        "role_setup",
        "format_ingestion",
        "retrieval_resource_proof",
        "post_rollback_baseline_verification",
    ],
    reason_code: Literal[
        "candidate_state_invalid",
        "sealed_input_invalid",
        "candidate_pair_invalid",
        "role_setup_failed",
        "format_ingestion_failed",
        "provider_request_failed",
        "resource_proof_failed",
        "rollback_proof_failed",
        "provider_execution_failed",
    ],
    run_identity_hash: str,
    completed_round_count: int,
    provider_request_count: int = 0,
    provider_request_classification: Literal[
        "not_attempted",
        "request_started",
        "request_completed",
        "request_failed",
    ] = "not_attempted",
    rollback_attempted: bool = False,
    rollback_proved: bool = False,
) -> SafeRoleFailureV1:
    return SafeRoleFailureV1(
        failing_role=role,
        round_format=round_format,
        stage=stage,
        reason_code=reason_code,
        provider_availability=("available" if provider_request_classification != "not_attempted" else "not_checked"),
        provider_request_classification=provider_request_classification,
        outer_rollback_attempted=rollback_attempted,
        outer_rollback_proved=rollback_proved,
        completed_round_count=completed_round_count,
        provider_request_count=provider_request_count,
        safe_context_sha256=f"sha256:{run_identity_hash}",
    )


class RecordingPolicyRetrievalEngine:
    """Forwards the service's one query and exposes one bounded observation."""

    def __init__(self, delegate: PolicyRetrievalEngine) -> None:
        self._delegate = delegate
        self._recording: PolicyRetrievalRun | None = None

    async def retrieve_run(self, **kwargs: Any) -> PolicyRetrievalRun:
        if self._recording is not None:
            raise EvaluationIsolationError("recording_not_consumed")
        run = await self._delegate.retrieve_run(**kwargs)
        self._recording = run
        return run

    def take_recording(self, *, expected_query: str) -> PolicyRetrievalRun:
        run = self._recording
        self._recording = None
        if run is None or run.original_query != expected_query:
            raise EvaluationIsolationError("retrieval_recording_mismatch")
        return run

    async def get_contents_by_evidence_keys(self, **kwargs: Any) -> dict[tuple[str, str], str]:
        """Forward the service's verified-provenance lookup without another retrieval."""

        return await self._delegate.get_contents_by_evidence_keys(**kwargs)

    async def get_provenance_by_evidence_keys(self, **kwargs: Any) -> dict[tuple[str, str], EvidenceProvenance]:
        """Forward locator resolution for evidence refs recorded by the one search."""

        return await self._delegate.get_provenance_by_evidence_keys(**kwargs)


def ordered_gold_questions(dataset: FormatParityDataset) -> tuple[tuple[str, str, str], ...]:
    return tuple(
        (policy.doc_key, case.case_id, case.question) for policy in dataset.policies for case in policy.gold.cases
    )


def build_knowledge_query(*, question: str, generated_at: str) -> tuple[KnowledgeSearchRequest, KnowledgeContext]:
    tenant = str(FORMAT_PARITY_TENANT_ID)
    request = KnowledgeSearchRequest(
        query=question,
        filters=KnowledgeSearchFilters(tenant_id=tenant, effective_at=generated_at),
        retrieval_config_version=RETRIEVAL_CONFIG_VERSION,
        rerank_config_version=RERANK_CONFIG_VERSION,
        max_results=5,
        allow_partial_evidence=True,
    )
    context = KnowledgeContext(
        tenant_id=tenant,
        user_id="rag-format-parity-evaluator",
        role="system_evaluator",
        merchant_scope=["*"],
        run_id="rag-format-parity",
        trace_id="rag-format-parity",
        locale="zh-CN",
        effective_at=generated_at,
    )
    if request.filters.tenant_id != tenant or context.tenant_id != tenant:
        raise EvaluationIsolationError("request_tenant_mismatch")
    return request, context


def _round_transaction(session: AsyncSession, *, rollback_only: bool):
    return session.begin_nested() if rollback_only else session.begin()


async def run_rollback_only_retrieval_parity(
    dataset: FormatParityDataset,
    *,
    session: AsyncSession,
    embedder: EmbeddingService,
    namespace: ABRoundNamespace,
    generated_at: str,
    run_identity_hash: str,
    expected_rollout_version: int,
    input_assembler: PolicyInputAssembler,
) -> RetrievalParityRunV1:
    """Run each format inside a rollback boundary proved against one baseline."""

    bind = session.bind
    if bind is None or not hasattr(bind, "connect"):
        raise SafeRoleExecutionError(
            _safe_role_failure(
                role=_diagnostic_role(namespace),
                round_format="markdown",
                stage="role_setup",
                reason_code="role_setup_failed",
                run_identity_hash=run_identity_hash,
                completed_round_count=0,
            )
        )
    try:
        baseline = await _capture_rollback_baseline(bind)
    except Exception:
        raise SafeRoleExecutionError(
            _safe_role_failure(
                role=_diagnostic_role(namespace),
                round_format="markdown",
                stage="role_setup",
                reason_code="role_setup_failed",
                run_identity_hash=run_identity_hash,
                completed_round_count=0,
            )
        ) from None
    proved_rounds: list[RetrievalRoundResultV1] = []
    first_run: RetrievalParityRunV1 | None = None
    for round_format in ROUND_FORMATS:
        isolated_run: RetrievalParityRunV1 | None = None
        execution_failure: SafeRoleFailureV1 | None = None
        rollback_attempted = False
        rollback_failed = False
        try:
            async with bind.connect() as connection:
                transaction = await connection.begin()
                rollback_session = AsyncSession(
                    bind=connection,
                    expire_on_commit=False,
                    join_transaction_mode="create_savepoint",
                )
                try:
                    async with rollback_session.begin():
                        repository = RagEvaluationRoundRepository(rollback_session)
                        owner = await repository.create_round(
                            run_token=namespace.run_token,
                            round_token=uuid5(NAMESPACE_URL, f"{namespace.run_token}:{round_format}"),
                            round_format=round_format,
                            run_identity_hash=run_identity_hash,
                            lease_expires_at=datetime.now(UTC) + timedelta(hours=2),
                            expected_rollout_version=expected_rollout_version,
                        )
                    isolated_run = await run_retrieval_parity(
                        dataset,
                        session=rollback_session,
                        embedder=embedder,
                        owner=owner,
                        generated_at=generated_at,
                        input_assembler=input_assembler,
                        rollback_only=True,
                        rollback_baseline=baseline,
                        stop_after_current_round=True,
                        failure_role=_diagnostic_role(namespace),
                    )
                except SafeRoleExecutionError as safe_error:
                    execution_failure = safe_error.failure
                except Exception:
                    execution_failure = _safe_role_failure(
                        role=_diagnostic_role(namespace),
                        round_format=round_format,
                        stage="role_setup",
                        reason_code="role_setup_failed",
                        run_identity_hash=run_identity_hash,
                        completed_round_count=len(proved_rounds),
                    )
                finally:
                    await rollback_session.close()
                    rollback_attempted = True
                    if transaction.is_active:
                        try:
                            await transaction.rollback()
                        except Exception:
                            rollback_failed = True
        except Exception:
            if execution_failure is None:
                execution_failure = _safe_role_failure(
                    role=_diagnostic_role(namespace),
                    round_format=round_format,
                    stage="role_setup",
                    reason_code="role_setup_failed",
                    run_identity_hash=run_identity_hash,
                    completed_round_count=len(proved_rounds),
                    rollback_attempted=rollback_attempted,
                )
        try:
            after = await _capture_rollback_baseline(bind)
            _require_rollback_baseline_unchanged(baseline, after)
        except Exception:
            raise SafeRoleExecutionError(
                _safe_role_failure(
                    role=_diagnostic_role(namespace),
                    round_format=round_format,
                    stage="post_rollback_baseline_verification",
                    reason_code="rollback_proof_failed",
                    run_identity_hash=run_identity_hash,
                    completed_round_count=len(proved_rounds),
                    rollback_attempted=rollback_attempted,
                )
            ) from None
        if rollback_failed:
            raise SafeRoleExecutionError(
                _safe_role_failure(
                    role=_diagnostic_role(namespace),
                    round_format=round_format,
                    stage="post_rollback_baseline_verification",
                    reason_code="rollback_proof_failed",
                    run_identity_hash=run_identity_hash,
                    completed_round_count=len(proved_rounds),
                    rollback_attempted=True,
                )
            )
        if execution_failure is not None:
            raise SafeRoleExecutionError(
                execution_failure.model_copy(
                    update={
                        "outer_rollback_attempted": rollback_attempted,
                        "outer_rollback_proved": rollback_attempted,
                    }
                )
            )
        if isolated_run is None or len(isolated_run.rounds) != 1:
            raise SafeRoleExecutionError(
                _safe_role_failure(
                    role=_diagnostic_role(namespace),
                    round_format=round_format,
                    stage="role_setup",
                    reason_code="role_setup_failed",
                    run_identity_hash=run_identity_hash,
                    completed_round_count=len(proved_rounds),
                    rollback_attempted=rollback_attempted,
                    rollback_proved=rollback_attempted,
                )
            )
        if first_run is None:
            first_run = isolated_run
        returned_round = isolated_run.rounds[0]
        if returned_round.outcome is EvaluationOutcome.EXECUTION_ERROR:
            failure = returned_round.safe_failure or _safe_role_failure(
                role=_diagnostic_role(namespace),
                round_format=round_format,
                stage="retrieval_resource_proof",
                reason_code="provider_execution_failed",
                run_identity_hash=run_identity_hash,
                completed_round_count=len(proved_rounds),
                provider_request_count=len(returned_round.cases),
                provider_request_classification="request_failed",
            )
            raise SafeRoleExecutionError(
                failure.model_copy(
                    update={
                        "outer_rollback_attempted": rollback_attempted,
                        "outer_rollback_proved": rollback_attempted,
                    }
                )
            )
        proved_round = returned_round.model_copy(
            update={"post_state_proved": True, "immutable_history_preserved": True}
        )
        proved_rounds.append(proved_round)

    if first_run is None:
        raise SafeRoleExecutionError(
            _safe_role_failure(
                role=_diagnostic_role(namespace),
                round_format=None,
                stage="role_setup",
                reason_code="role_setup_failed",
                run_identity_hash=run_identity_hash,
                completed_round_count=0,
            )
        )
    overall = _overall_outcome(proved_rounds)
    return first_run.model_copy(
        update={
            "baseline_eligible": overall
            in {EvaluationOutcome.COMPLETED_PASS, EvaluationOutcome.COMPLETED_QUALITY_FAIL},
            "outcome": overall,
            "rounds": tuple(proved_rounds),
        }
    )


async def _capture_rollback_baseline(bind: object) -> RollbackBaselineProof:
    async with AsyncSession(bind=bind, expire_on_commit=False) as read_session:
        try:
            return await RagEvaluationRoundRepository(read_session).capture_rollback_baseline()
        finally:
            await read_session.rollback()


def _require_rollback_baseline_unchanged(
    before: RollbackBaselineProof,
    after: RollbackBaselineProof,
) -> None:
    if before != after:
        raise EvaluationIsolationError("rollback_baseline_mismatch")


async def run_retrieval_parity(
    dataset: FormatParityDataset,
    *,
    session: AsyncSession,
    embedder: EmbeddingService,
    owner: EvaluationRoundIdentity,
    generated_at: str,
    input_assembler: PolicyInputAssembler | None = None,
    rollback_only: bool = False,
    rollback_baseline: RollbackBaselineProof | None = None,
    stop_after_current_round: bool = False,
    failure_role: Literal["character_incumbent", "token_candidate"] | None = None,
) -> RetrievalParityRunV1:
    """Run the real production ingestion and knowledge facade in three rounds."""

    if owner.tenant_id != FORMAT_PARITY_TENANT_ID or owner.owner_marker != FORMAT_PARITY_OWNER_MARKER:
        raise EvaluationIsolationError("identity_mismatch")
    if owner.round_format not in ROUND_FORMATS:
        raise EvaluationIsolationError("initial_round_mismatch")
    if rollback_only != (rollback_baseline is not None) or (stop_after_current_round and not rollback_only):
        raise EvaluationIsolationError("rollback_baseline_invalid")
    ingestion_service = IngestionService(
        session,
        embedder,
        FORMAT_PARITY_TENANT_ID,
        assembly_mode=IngestionAssemblyMode.TOKEN_AWARE,
        input_assembler=input_assembler or PolicyEmbeddingInputAssembler(),
    )
    recording_engine = RecordingPolicyRetrievalEngine(PolicyRetrievalEngine(session, embedder=embedder))
    knowledge_service = PolicyKnowledgeService(recording_engine)
    round_repo = RagEvaluationRoundRepository(session)
    current_owner = owner
    start_index = ROUND_FORMATS.index(owner.round_format)
    round_results: list[RetrievalRoundResultV1] = []
    if start_index and not stop_after_current_round:
        async with _round_transaction(session, rollback_only=rollback_only):
            sequence = validate_run_sequence(
                await round_repo.lock_run_rows(owner.run_token),
                run_token=owner.run_token,
                expected_rollout_version=owner.expected_rollout_version,
                run_identity_hash=owner.run_identity_hash,
                now=datetime.now(UTC),
            )
        if sequence.active != owner or len(sequence.completed_results) != start_index:
            raise EvaluationIsolationError("resume_sequence_mismatch")
        try:
            round_results.extend(
                RetrievalRoundResultV1.model_validate(payload) for payload in sequence.completed_results
            )
        except ValueError:
            raise EvaluationIsolationError("terminal_round_result_invalid") from None

    for format_index, round_format in enumerate(ROUND_FORMATS[start_index:], start=start_index):
        if current_owner.round_format != round_format:
            raise EvaluationIsolationError("round_format_mismatch")
        ingestions: list[IngestionObservationV1] = []
        observations: list[RetrievalCaseObservationV1] = []
        terminal_outcome = EvaluationOutcome.COMPLETED_PASS
        failure_reason: str | None = None
        safe_failure: SafeRoleFailureV1 | None = None
        failure_stage: Literal["format_ingestion", "retrieval_resource_proof"] = "format_ingestion"
        pre_state_proved = False
        post_state_proved = False
        immutable_preserved = False
        ingestion_quality_failed = False
        successful_round: RetrievalRoundResultV1 | None = None
        try:
            async with _round_transaction(session, rollback_only=rollback_only):
                progress = await round_repo.read_progress(current_owner)
            if progress.state == "claimed":
                if current_owner.next_document_index != 0 or progress.has_attempt_reservation:
                    raise EvaluationIsolationError("claimed_progress_malformed")
                async with _round_transaction(session, rollback_only=rollback_only):
                    if rollback_baseline is None:
                        current_owner = await round_repo.prove_compatible_pre_state(current_owner)
                    else:
                        current_owner = await round_repo.prove_compatible_pre_state(
                            current_owner,
                            rollback_baseline=rollback_baseline,
                        )
                progress_state = "ingesting"
            elif progress.state in {"ingesting", "retrieving"}:
                progress_state = progress.state
            else:
                raise EvaluationIsolationError("round_not_resumable")
            pre_state_proved = True
            for document_index, policy in enumerate(dataset.policies):
                variant = next(item for item in policy.variants if item.format == round_format)
                if document_index < current_owner.next_document_index:
                    async with _round_transaction(session, rollback_only=rollback_only):
                        resource_reader = getattr(round_repo, "prove_advanced_document_resources", None)
                        if callable(resource_reader):
                            current_owner, resources = await resource_reader(
                                current_owner,
                                doc_key=policy.doc_key,
                                source_checksum=variant.sha256,
                            )
                        else:
                            current_owner = await round_repo.prove_advanced_document(
                                current_owner,
                                doc_key=policy.doc_key,
                                source_checksum=variant.sha256,
                            )
                            resources = IngestionResourceProof(
                                chunk_count=0,
                                duplicate_count=0,
                                offline_embedding_tokens=0,
                                provider_embedding_tokens=None,
                                provider_tokens_status="unavailable",
                                config_fingerprint=None,
                            )
                    ingestions.append(
                        IngestionObservationV1(
                            doc_key=policy.doc_key,
                            source_checksum=variant.sha256,
                            status="success",
                            chunk_count=resources.chunk_count,
                            duplicate_count=resources.duplicate_count,
                            offline_embedding_tokens=resources.offline_embedding_tokens,
                            provider_embedding_tokens=resources.provider_embedding_tokens,
                            provider_tokens_status=resources.provider_tokens_status,
                            config_fingerprint=resources.config_fingerprint,
                        )
                    )
                    continue
                if progress_state == "retrieving":
                    raise EvaluationIsolationError("retrieval_progress_mismatch")
                source_path = Path(variant.path)
                doc_meta = {
                    "doc_key": policy.doc_key,
                    "title": policy.title,
                    "doc_type": "evaluation_policy",
                    "risk_level": "low",
                    "effective_date": date.fromisoformat("2026-01-01"),
                    "source_type": variant.source_type,
                }
                async with _round_transaction(session, rollback_only=rollback_only):
                    current_progress = await round_repo.read_progress(current_owner)
                if current_progress.has_attempt_reservation:
                    report = None
                else:
                    async with _round_transaction(session, rollback_only=rollback_only):
                        current_owner = await round_repo.reserve_document(
                            current_owner,
                            doc_key=policy.doc_key,
                            source_checksum=variant.sha256,
                            reserved_at=datetime.now(UTC),
                        )
                    report = await ingestion_service.ingest_document(
                        source_path,
                        doc_meta,
                        expected_rollout_version=current_owner.expected_rollout_version,
                    )
                current_owner, observation, ingestion_error = await _resolve_ingestion_attempt(
                    session=session,
                    round_repo=round_repo,
                    ingestion_service=ingestion_service,
                    owner=current_owner,
                    round_format=round_format,
                    source_path=source_path,
                    source_checksum=variant.sha256,
                    doc_meta=doc_meta,
                    first_report=report,
                    rollback_only=rollback_only,
                )
                ingestions.append(observation)
                if ingestion_error is not None:
                    raise EvaluationIsolationError(ingestion_error)
                ingestion_quality_failed = ingestion_quality_failed or observation.status == "failed"

            if ingestion_quality_failed:
                terminal_outcome = EvaluationOutcome.COMPLETED_QUALITY_FAIL
            else:
                failure_stage = "retrieval_resource_proof"
                async with _round_transaction(session, rollback_only=rollback_only):
                    if rollback_baseline is None:
                        current_owner = await round_repo.prove_retrieval_ready(current_owner)
                    else:
                        current_owner = await round_repo.prove_retrieval_ready(
                            current_owner,
                            rollback_baseline=rollback_baseline,
                        )
                for policy in dataset.policies:
                    anchors_by_id = {anchor.anchor_id: anchor for anchor in policy.gold.anchors}
                    for case in policy.gold.cases:
                        request, context = build_knowledge_query(
                            question=case.question,
                            generated_at=generated_at,
                        )
                        async with _round_transaction(session, rollback_only=rollback_only):
                            current_owner = await round_repo.prove_run_identity(current_owner)
                            service_result = await knowledge_service.search(request, context)
                            recorded = recording_engine.take_recording(expected_query=case.question)
                            provenance = await knowledge_service.get_verified_evidence_provenance(
                                tenant_id=str(FORMAT_PARITY_TENANT_ID),
                                evidence_refs=recorded.evidence_refs,
                            )
                            locator_covered = case.locator_constraints is None or await _recorded_locator_satisfies(
                                round_repo,
                                recorded,
                                provenance_by_evidence_id=provenance,
                                doc_key=policy.doc_key,
                                expected_anchors=[
                                    AnchorLocatorRequirement(
                                        text=anchors_by_id[anchor_id].text,
                                        section=anchors_by_id[anchor_id].section,
                                    )
                                    for anchor_id in case.evidence_anchor_ids
                                ],
                                allowed_pdf_pages=(
                                    case.locator_constraints.pdf_pages
                                    if round_format in {"digital_pdf", "scanned_pdf"}
                                    and case.locator_constraints is not None
                                    else ()
                                ),
                            )
                        observations.append(
                            _case_observation(
                                policy_id=policy.doc_key,
                                round_format=round_format,
                                case=case,
                                anchors_by_id={key: anchor.text for key, anchor in anchors_by_id.items()},
                                service_result=service_result,
                                recorded=recorded,
                                locator_covered=locator_covered,
                            )
                        )
                if any(not _case_quality_pass(case) for case in observations):
                    terminal_outcome = EvaluationOutcome.COMPLETED_QUALITY_FAIL
            successful_round = RetrievalRoundResultV1(
                round_format=round_format,
                round_token=str(current_owner.round_token),
                outcome=terminal_outcome,
                ingestions=tuple(ingestions),
                cases=tuple(observations),
                pre_state_proved=pre_state_proved,
                exactly_three_current_proved=len(ingestions) == 3
                and all(observation.status == "success" for observation in ingestions),
                post_state_proved=not rollback_only,
                immutable_history_preserved=not rollback_only,
            )
            async with _round_transaction(session, rollback_only=rollback_only):
                if rollback_baseline is None:
                    current_owner = await round_repo.cleanup_current_projection(
                        current_owner,
                        terminal_state="completed",
                        round_result=successful_round.model_dump(mode="json"),
                    )
                else:
                    current_owner = await round_repo.cleanup_current_projection(
                        current_owner,
                        terminal_state="completed",
                        round_result=successful_round.model_dump(mode="json"),
                        rollback_baseline=rollback_baseline,
                    )
            post_state_proved = not rollback_only
            immutable_preserved = not rollback_only
        except EvaluationIsolationError as isolation_error:
            terminal_outcome = EvaluationOutcome.EXECUTION_ERROR
            failure_reason = isolation_error.reason_code
            if failure_role is not None:
                safe_failure = _safe_role_failure(
                    role=failure_role,
                    round_format=round_format,
                    stage=failure_stage,
                    reason_code=(
                        "format_ingestion_failed" if failure_stage == "format_ingestion" else "resource_proof_failed"
                    ),
                    run_identity_hash=owner.run_identity_hash,
                    completed_round_count=len(round_results),
                    provider_request_count=len(observations),
                    provider_request_classification=(
                        "not_attempted" if failure_stage == "format_ingestion" else "request_completed"
                    ),
                )
            try:
                async with _round_transaction(session, rollback_only=rollback_only):
                    if rollback_baseline is None:
                        current_owner = await round_repo.cleanup_current_projection(
                            current_owner,
                            terminal_state="abandoned",
                            failure_code=failure_reason,
                        )
                    else:
                        current_owner = await round_repo.cleanup_current_projection(
                            current_owner,
                            terminal_state="abandoned",
                            failure_code=failure_reason,
                            rollback_baseline=rollback_baseline,
                        )
                post_state_proved = not rollback_only
                immutable_preserved = not rollback_only
            except Exception:
                failure_reason = "cleanup_proof_failed"
                if failure_role is not None:
                    safe_failure = _safe_role_failure(
                        role=failure_role,
                        round_format=round_format,
                        stage="retrieval_resource_proof",
                        reason_code="resource_proof_failed",
                        run_identity_hash=owner.run_identity_hash,
                        completed_round_count=len(round_results),
                        provider_request_count=len(observations),
                        provider_request_classification=("not_attempted" if not observations else "request_completed"),
                    )
        except Exception:
            terminal_outcome = EvaluationOutcome.EXECUTION_ERROR
            failure_reason = "provider_execution_failed"
            if failure_role is not None:
                safe_failure = _safe_role_failure(
                    role=failure_role,
                    round_format=round_format,
                    stage=failure_stage,
                    reason_code=(
                        "provider_request_failed"
                        if failure_stage == "retrieval_resource_proof"
                        else "format_ingestion_failed"
                    ),
                    run_identity_hash=owner.run_identity_hash,
                    completed_round_count=len(round_results),
                    provider_request_count=len(observations) + 1,
                    provider_request_classification="request_failed",
                )
            try:
                async with _round_transaction(session, rollback_only=rollback_only):
                    if rollback_baseline is None:
                        current_owner = await round_repo.cleanup_current_projection(
                            current_owner,
                            terminal_state="abandoned",
                            failure_code=failure_reason,
                        )
                    else:
                        current_owner = await round_repo.cleanup_current_projection(
                            current_owner,
                            terminal_state="abandoned",
                            failure_code=failure_reason,
                            rollback_baseline=rollback_baseline,
                        )
                post_state_proved = not rollback_only
                immutable_preserved = not rollback_only
            except Exception:
                failure_reason = "cleanup_proof_failed"
                if failure_role is not None:
                    safe_failure = _safe_role_failure(
                        role=failure_role,
                        round_format=round_format,
                        stage="retrieval_resource_proof",
                        reason_code="resource_proof_failed",
                        run_identity_hash=owner.run_identity_hash,
                        completed_round_count=len(round_results),
                        provider_request_count=len(observations) + 1,
                        provider_request_classification="request_failed",
                    )

        round_results.append(
            successful_round
            if successful_round is not None and terminal_outcome is not EvaluationOutcome.EXECUTION_ERROR
            else RetrievalRoundResultV1(
                round_format=round_format,
                round_token=str(current_owner.round_token),
                outcome=terminal_outcome,
                ingestions=tuple(ingestions),
                cases=tuple(observations),
                pre_state_proved=pre_state_proved,
                exactly_three_current_proved=len(ingestions) == 3
                and all(observation.status == "success" for observation in ingestions),
                post_state_proved=post_state_proved,
                immutable_history_preserved=immutable_preserved,
                reason_code=failure_reason,
                safe_failure=safe_failure,
            )
        )
        if terminal_outcome is EvaluationOutcome.EXECUTION_ERROR:
            break
        if stop_after_current_round:
            break
        if format_index + 1 < len(ROUND_FORMATS):
            next_format = ROUND_FORMATS[format_index + 1]
            async with _round_transaction(session, rollback_only=rollback_only):
                current_owner = await round_repo.create_round(
                    run_token=owner.run_token,
                    round_token=uuid5(NAMESPACE_URL, f"{owner.run_token}:{next_format}"),
                    round_format=next_format,
                    run_identity_hash=owner.run_identity_hash,
                    lease_expires_at=datetime.now(UTC) + timedelta(hours=2),
                    expected_rollout_version=owner.expected_rollout_version,
                )

    overall = _overall_outcome(round_results)
    return RetrievalParityRunV1(
        mode="provider",
        baseline_eligible=overall in {EvaluationOutcome.COMPLETED_PASS, EvaluationOutcome.COMPLETED_QUALITY_FAIL},
        outcome=overall,
        generated_at=generated_at,
        tenant_id=str(FORMAT_PARITY_TENANT_ID),
        owner_marker=FORMAT_PARITY_OWNER_MARKER,
        run_token=str(owner.run_token),
        manifest_hash=dataset.manifest_hash,
        gold_hash=dataset.gold_hash,
        baseline_identity=dataset.baseline_identity,
        rounds=tuple(round_results),
        prerequisites=(
            PrerequisiteStatusV1(name="postgresql_pgvector", available=True),
            PrerequisiteStatusV1(name="embedding_provider", available=True),
            PrerequisiteStatusV1(name="tesseract_chi_sim_eng", available=True),
        ),
    )


def rebuild_completed_retrieval_parity(
    dataset: FormatParityDataset,
    *,
    completed_results: tuple[dict[str, Any], ...],
    generated_at: str,
    run_token: UUID,
    run_identity_hash: str,
    expected_run_identity_hash: str,
) -> RetrievalParityRunV1:
    """Rebuild a completed run from strict terminal proofs without provider mutation."""

    if run_identity_hash != expected_run_identity_hash:
        raise EvaluationIsolationError("run_identity_mismatch")
    try:
        rounds = tuple(RetrievalRoundResultV1.model_validate(payload) for payload in completed_results)
    except ValueError:
        raise EvaluationIsolationError("terminal_round_result_invalid") from None
    expected_tokens = tuple(str(uuid5(NAMESPACE_URL, f"{run_token}:{name}")) for name in ROUND_FORMATS)
    if (
        tuple(item.round_format for item in rounds) != ROUND_FORMATS
        or tuple(item.round_token for item in rounds) != expected_tokens
        or any(
            item.outcome not in {EvaluationOutcome.COMPLETED_PASS, EvaluationOutcome.COMPLETED_QUALITY_FAIL}
            for item in rounds
        )
    ):
        raise EvaluationIsolationError("terminal_round_result_invalid")
    overall = _overall_outcome(list(rounds))
    return RetrievalParityRunV1(
        mode="provider",
        baseline_eligible=True,
        outcome=overall,
        generated_at=generated_at,
        tenant_id=str(FORMAT_PARITY_TENANT_ID),
        owner_marker=FORMAT_PARITY_OWNER_MARKER,
        run_token=str(run_token),
        manifest_hash=dataset.manifest_hash,
        gold_hash=dataset.gold_hash,
        baseline_identity=dataset.baseline_identity,
        rounds=rounds,
        prerequisites=(
            PrerequisiteStatusV1(name="postgresql_pgvector", available=True),
            PrerequisiteStatusV1(name="embedding_provider", available=True),
            PrerequisiteStatusV1(name="tesseract_chi_sim_eng", available=True),
        ),
    )


async def _resolve_ingestion_attempt(
    *,
    session: AsyncSession,
    round_repo: RagEvaluationRoundRepository,
    ingestion_service: IngestionService,
    owner: EvaluationRoundIdentity,
    round_format: str,
    source_path: Path,
    source_checksum: str,
    doc_meta: dict[str, Any],
    first_report: object,
    rollback_only: bool = False,
) -> tuple[EvaluationRoundIdentity, IngestionObservationV1, str | None]:
    report = first_report
    real_report_count = int(report is not None)
    for _inspection_attempt in range(3):
        async with _round_transaction(session, rollback_only=rollback_only):
            inspection = await round_repo.inspect_attempt(owner)
        if inspection.state is ProjectionState.EXACT_COMPLETE:
            async with _round_transaction(session, rollback_only=rollback_only):
                owner = await round_repo.claim_attempt_job(owner, require_null_document=False)
            async with _round_transaction(session, rollback_only=rollback_only):
                owner = await round_repo.advance_exact_complete(owner)
            resources = getattr(
                inspection,
                "resources",
                IngestionResourceProof(
                    chunk_count=int(getattr(inspection.projection, "chunk_count", 0)),
                    duplicate_count=0,
                    offline_embedding_tokens=0,
                    provider_embedding_tokens=None,
                    provider_tokens_status="unavailable",
                    config_fingerprint=None,
                ),
            )
            return (
                owner,
                IngestionObservationV1(
                    doc_key=str(doc_meta["doc_key"]),
                    source_checksum=source_checksum,
                    status="success",
                    chunk_count=resources.chunk_count,
                    duplicate_count=resources.duplicate_count,
                    offline_embedding_tokens=resources.offline_embedding_tokens,
                    provider_embedding_tokens=resources.provider_embedding_tokens,
                    provider_tokens_status=resources.provider_tokens_status,
                    config_fingerprint=resources.config_fingerprint,
                ),
                None,
            )
        if inspection.state in {ProjectionState.JOB_ONLY, ProjectionState.FAILURE}:
            if report is None:
                real_report_count = max(real_report_count, 1)
            async with _round_transaction(session, rollback_only=rollback_only):
                owner = await round_repo.claim_attempt_job(
                    owner,
                    require_null_document=inspection.state is ProjectionState.JOB_ONLY,
                )
            error_code = str(getattr(report, "error_code", None) or "ingestion_failed")
            if (
                real_report_count >= 2
                and inspection.state is ProjectionState.FAILURE
                and round_format == "scanned_pdf"
                and error_code == "malformed_source"
            ):
                async with _round_transaction(session, rollback_only=rollback_only):
                    owner = await round_repo.advance_exact_failed_quality(
                        owner,
                        error_code=error_code,
                    )
                return (
                    owner,
                    IngestionObservationV1(
                        doc_key=str(doc_meta["doc_key"]),
                        source_checksum=source_checksum,
                        status="failed",
                        error_code=error_code,
                    ),
                    None,
                )
            async with _round_transaction(session, rollback_only=rollback_only):
                owner = await round_repo.retry_attempt(owner)
        elif inspection.state is not ProjectionState.RESERVATION_ONLY:
            raise EvaluationIsolationError("malformed_projection")
        if real_report_count >= 2:
            error_code = str(getattr(report, "error_code", None) or "ingestion_failed")
            return (
                owner,
                IngestionObservationV1(
                    doc_key=str(doc_meta["doc_key"]),
                    source_checksum=source_checksum,
                    status="failed",
                    error_code=error_code,
                ),
                f"ingestion_failed:{error_code}",
            )
        async with _round_transaction(session, rollback_only=rollback_only):
            owner = await round_repo.reserve_document(
                owner,
                doc_key=str(doc_meta["doc_key"]),
                source_checksum=source_checksum,
                reserved_at=datetime.now(UTC),
            )
        report = await ingestion_service.ingest_document(
            source_path,
            doc_meta,
            expected_rollout_version=owner.expected_rollout_version,
        )
        real_report_count += 1
    raise AssertionError("ingestion attempt loop exhausted")


def _case_observation(
    *,
    policy_id: str,
    round_format: str,
    case: SemanticCase,
    anchors_by_id: dict[str, str],
    service_result: object,
    recorded: PolicyRetrievalRun,
    locator_covered: bool,
) -> RetrievalCaseObservationV1:
    ranked_doc_keys = tuple(hit.doc_key for hit in recorded.hits[:5])
    expected_rank = next(
        (index for index, doc_key in enumerate(ranked_doc_keys, start=1) if doc_key == policy_id),
        None,
    )
    expected_anchors = [anchors_by_id[anchor_id] for anchor_id in case.evidence_anchor_ids]
    hit_text = "\n".join(hit.text for hit in recorded.hits if hit.doc_key == policy_id)
    anchor_hits = sum(anchor in hit_text for anchor in expected_anchors)
    no_answer_correct = bool(case.no_answer and getattr(service_result, "status", None) == "no_evidence")
    locator_covered = case.locator_constraints is None or locator_covered
    return RetrievalCaseObservationV1(
        policy_id=policy_id,
        case_id=case.case_id,
        question=case.question,
        category=case.category,
        service_status=str(getattr(service_result, "status", "error")),
        ranked_doc_keys=ranked_doc_keys,
        hit_at_1=expected_rank == 1,
        hit_at_3=expected_rank is not None and expected_rank <= 3,
        hit_at_5=expected_rank is not None and expected_rank <= 5,
        reciprocal_rank=0.0 if expected_rank is None else 1.0 / expected_rank,
        semantic_anchor_hits=anchor_hits,
        semantic_anchor_total=len(expected_anchors),
        no_answer_correct=no_answer_correct,
        locator_expected=case.locator_constraints is not None,
        locator_covered=locator_covered,
        query_rewrite=getattr(service_result, "query_rewrite", None),
        fallback_reason=recorded.fallback_reason,
        rerank_observed=recorded.diagnostics is not None,
    )


async def _recorded_locator_satisfies(
    round_repo: RagEvaluationRoundRepository,
    recorded: PolicyRetrievalRun,
    *,
    provenance_by_evidence_id: dict[str, EvidenceProvenance],
    doc_key: str,
    expected_anchors: list[AnchorLocatorRequirement],
    allowed_pdf_pages: tuple[int, ...],
) -> bool:
    """Fail closed unless exact recorded chunks and source blocks prove every anchor."""

    refs_by_chunk: dict[str, list[Any]] = {}
    for ref in recorded.evidence_refs:
        if ref.doc_key == doc_key:
            refs_by_chunk.setdefault(ref.chunk_id, []).append(ref)
    candidates: list[RecordedChunkLocatorProof] = []
    for hit in recorded.hits:
        if hit.doc_key != doc_key or not any(item.text in hit.text for item in expected_anchors):
            continue
        refs = refs_by_chunk.get(hit.chunk_id, [])
        if len(refs) != 1:
            continue
        ref = refs[0]
        if evidence_text_hash(hit.text) != ref.text_hash:
            continue
        provenance = provenance_by_evidence_id.get(ref.evidence_id)
        if (
            provenance is None
            or provenance.doc_key != ref.doc_key
            or provenance.chunk_id != ref.chunk_id
            or provenance.evidence_id != ref.evidence_id
        ):
            continue
        candidates.append(
            RecordedChunkLocatorProof(
                chunk_id=hit.chunk_id,
                text_hash=ref.text_hash,
                source_locators=tuple(
                    RecordedSourceLocatorProof(
                        source_block_id=locator.source_block_id,
                        page_number=locator.page_number,
                    )
                    for locator in provenance.source_locators
                    if locator.source_block_id
                ),
            )
        )
    if not candidates:
        return False
    return await round_repo.prove_recorded_anchor_locators(
        doc_key=doc_key,
        candidates=candidates,
        requirements=expected_anchors,
        allowed_pdf_pages=allowed_pdf_pages,
    )


def _case_quality_pass(case: RetrievalCaseObservationV1) -> bool:
    if case.category == "no_answer":
        return case.no_answer_correct
    return case.hit_at_5 and case.semantic_anchor_hits == case.semantic_anchor_total and case.locator_covered


def _overall_outcome(rounds: list[RetrievalRoundResultV1]) -> EvaluationOutcome:
    if any(item.outcome is EvaluationOutcome.EXECUTION_ERROR for item in rounds):
        return EvaluationOutcome.EXECUTION_ERROR
    if len(rounds) != len(ROUND_FORMATS):
        return EvaluationOutcome.EXECUTION_ERROR
    if any(item.outcome is EvaluationOutcome.COMPLETED_QUALITY_FAIL for item in rounds):
        return EvaluationOutcome.COMPLETED_QUALITY_FAIL
    return EvaluationOutcome.COMPLETED_PASS
