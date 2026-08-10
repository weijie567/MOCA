"""Provider-backed, evaluation-owned retrieval format-parity orchestration."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any, Literal
from uuid import NAMESPACE_URL, uuid5

from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy.ext.asyncio import AsyncSession

from src.knowledge.config import RERANK_CONFIG_VERSION, RETRIEVAL_CONFIG_VERSION
from src.knowledge.retrieval import PolicyRetrievalEngine, PolicyRetrievalRun
from src.knowledge.schemas import (
    KnowledgeContext,
    KnowledgeSearchFilters,
    KnowledgeSearchRequest,
)
from src.knowledge.service import PolicyKnowledgeService
from src.rag.embedder import EmbeddingService
from src.rag.evaluation.contracts import EvaluationOutcome, FormatParityDataset, SemanticCase
from src.rag.ingestion import IngestionService
from src.repositories.rag_evaluation_round_repo import (
    FORMAT_PARITY_OWNER_MARKER,
    FORMAT_PARITY_TENANT_ID,
    ROUND_FORMATS,
    EvaluationIsolationError,
    EvaluationRoundIdentity,
    ProjectionState,
    RagEvaluationRoundRepository,
)


class PrerequisiteStatusV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(min_length=1, max_length=64)
    available: bool
    reason_code: str | None = Field(default=None, max_length=64)


class IngestionObservationV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    doc_key: str
    source_checksum: str = Field(pattern=r"^[0-9a-f]{64}$")
    status: Literal["success", "failed"]
    error_code: str | None = None


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


async def run_retrieval_parity(
    dataset: FormatParityDataset,
    *,
    session: AsyncSession,
    embedder: EmbeddingService,
    owner: EvaluationRoundIdentity,
    generated_at: str,
) -> RetrievalParityRunV1:
    """Run the real production ingestion and knowledge facade in three rounds."""

    if owner.tenant_id != FORMAT_PARITY_TENANT_ID or owner.owner_marker != FORMAT_PARITY_OWNER_MARKER:
        raise EvaluationIsolationError("identity_mismatch")
    if owner.round_format != ROUND_FORMATS[0] or owner.next_document_index != 0:
        raise EvaluationIsolationError("initial_round_mismatch")
    ingestion_service = IngestionService(session, embedder, FORMAT_PARITY_TENANT_ID)
    recording_engine = RecordingPolicyRetrievalEngine(PolicyRetrievalEngine(session, embedder=embedder))
    knowledge_service = PolicyKnowledgeService(recording_engine)
    round_repo = RagEvaluationRoundRepository(session)
    current_owner = owner
    round_results: list[RetrievalRoundResultV1] = []

    for format_index, round_format in enumerate(ROUND_FORMATS):
        if current_owner.round_format != round_format:
            raise EvaluationIsolationError("round_format_mismatch")
        ingestions: list[IngestionObservationV1] = []
        observations: list[RetrievalCaseObservationV1] = []
        terminal_outcome = EvaluationOutcome.COMPLETED_PASS
        failure_reason: str | None = None
        pre_state_proved = False
        post_state_proved = False
        immutable_preserved = False
        try:
            async with session.begin():
                current_owner = await round_repo.prove_compatible_pre_state(current_owner)
            pre_state_proved = True
            for policy in dataset.policies:
                variant = next(item for item in policy.variants if item.format == round_format)
                source_path = Path(variant.path)
                async with session.begin():
                    current_owner = await round_repo.reserve_document(
                        current_owner,
                        doc_key=policy.doc_key,
                        source_checksum=variant.sha256,
                        reserved_at=datetime.now(UTC),
                    )
                report = await ingestion_service.ingest_document(
                    source_path,
                    {
                        "doc_key": policy.doc_key,
                        "title": policy.title,
                        "doc_type": "evaluation_policy",
                        "risk_level": "low",
                        "effective_date": date.fromisoformat("2026-01-01"),
                        "source_type": variant.source_type,
                    },
                    expected_rollout_version=current_owner.expected_rollout_version,
                )
                current_owner, observation = await _resolve_ingestion_attempt(
                    session=session,
                    round_repo=round_repo,
                    ingestion_service=ingestion_service,
                    owner=current_owner,
                    source_path=source_path,
                    source_checksum=variant.sha256,
                    doc_meta={
                        "doc_key": policy.doc_key,
                        "title": policy.title,
                        "doc_type": "evaluation_policy",
                        "risk_level": "low",
                        "effective_date": date.fromisoformat("2026-01-01"),
                        "source_type": variant.source_type,
                    },
                    first_report=report,
                )
                ingestions.append(observation)

            async with session.begin():
                current_owner = await round_repo.prove_retrieval_ready(current_owner)
            for policy in dataset.policies:
                anchors_by_id = {anchor.anchor_id: anchor.text for anchor in policy.gold.anchors}
                for case in policy.gold.cases:
                    request, context = build_knowledge_query(
                        question=case.question,
                        generated_at=generated_at,
                    )
                    service_result = await knowledge_service.search(request, context)
                    recorded = recording_engine.take_recording(expected_query=case.question)
                    observations.append(
                        _case_observation(
                            policy_id=policy.doc_key,
                            case=case,
                            anchors_by_id=anchors_by_id,
                            service_result=service_result,
                            recorded=recorded,
                        )
                    )
            if any(not _case_quality_pass(case) for case in observations):
                terminal_outcome = EvaluationOutcome.COMPLETED_QUALITY_FAIL
            async with session.begin():
                current_owner = await round_repo.cleanup_current_projection(
                    current_owner,
                    terminal_state="completed",
                )
            post_state_proved = True
            immutable_preserved = True
        except Exception as exc:
            terminal_outcome = EvaluationOutcome.EXECUTION_ERROR
            failure_reason = (
                exc.reason_code if isinstance(exc, EvaluationIsolationError) else "provider_execution_failed"
            )
            try:
                async with session.begin():
                    current_owner = await round_repo.cleanup_current_projection(
                        current_owner,
                        terminal_state="abandoned",
                        failure_code=failure_reason,
                    )
                post_state_proved = True
                immutable_preserved = True
            except Exception:
                failure_reason = "cleanup_proof_failed"

        round_results.append(
            RetrievalRoundResultV1(
                round_format=round_format,
                round_token=str(current_owner.round_token),
                outcome=terminal_outcome,
                ingestions=tuple(ingestions),
                cases=tuple(observations),
                pre_state_proved=pre_state_proved,
                exactly_three_current_proved=len(ingestions) == 3,
                post_state_proved=post_state_proved,
                immutable_history_preserved=immutable_preserved,
                reason_code=failure_reason,
            )
        )
        if terminal_outcome is EvaluationOutcome.EXECUTION_ERROR:
            break
        if format_index + 1 < len(ROUND_FORMATS):
            next_format = ROUND_FORMATS[format_index + 1]
            async with session.begin():
                current_owner = await round_repo.create_round(
                    run_token=owner.run_token,
                    round_token=uuid5(NAMESPACE_URL, f"{owner.run_token}:{next_format}"),
                    round_format=next_format,
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


async def _resolve_ingestion_attempt(
    *,
    session: AsyncSession,
    round_repo: RagEvaluationRoundRepository,
    ingestion_service: IngestionService,
    owner: EvaluationRoundIdentity,
    source_path: Path,
    source_checksum: str,
    doc_meta: dict[str, Any],
    first_report: object,
) -> tuple[EvaluationRoundIdentity, IngestionObservationV1]:
    report = first_report
    for attempt in range(2):
        async with session.begin():
            inspection = await round_repo.inspect_attempt(owner)
        if inspection.state is ProjectionState.EXACT_COMPLETE:
            async with session.begin():
                owner = await round_repo.claim_attempt_job(owner, require_null_document=False)
            async with session.begin():
                owner = await round_repo.advance_exact_complete(owner)
            return owner, IngestionObservationV1(
                doc_key=str(doc_meta["doc_key"]),
                source_checksum=source_checksum,
                status="success",
            )
        if inspection.state in {ProjectionState.JOB_ONLY, ProjectionState.FAILURE}:
            async with session.begin():
                owner = await round_repo.claim_attempt_job(
                    owner,
                    require_null_document=inspection.state is ProjectionState.JOB_ONLY,
                )
            async with session.begin():
                owner = await round_repo.retry_attempt(owner)
        elif inspection.state is not ProjectionState.RESERVATION_ONLY:
            raise EvaluationIsolationError("malformed_projection")
        if attempt == 1:
            break
        async with session.begin():
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
    error_code = str(getattr(report, "error_code", None) or "ingestion_failed")
    raise EvaluationIsolationError(f"ingestion_failed:{error_code}")


def _case_observation(
    *,
    policy_id: str,
    case: SemanticCase,
    anchors_by_id: dict[str, str],
    service_result: object,
    recorded: PolicyRetrievalRun,
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
        locator_covered=case.locator_constraints is None or expected_rank is not None,
        query_rewrite=getattr(service_result, "query_rewrite", None),
        fallback_reason=recorded.fallback_reason,
        rerank_observed=recorded.diagnostics is not None,
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
