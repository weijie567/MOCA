from __future__ import annotations

import inspect
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from sqlalchemy.dialects import postgresql

from src.db.models import RagEvaluationRound
from src.repositories.rag_evaluation_round_repo import (
    FORMAT_PARITY_DOC_KEYS,
    FORMAT_PARITY_OWNER_MARKER,
    FORMAT_PARITY_TENANT_ID,
    ROUND_FORMATS,
    AttemptProjection,
    EvaluationIsolationError,
    EvaluationRoundIdentity,
    ProjectionState,
    RagEvaluationRoundRepository,
    classify_attempt_projection,
)
from src.repositories.rag_ingestion_job_repo import RagIngestionJobRepository
from src.knowledge.retrieval import PolicyRetrievalRun
from src.knowledge.schemas import KnowledgeContext, KnowledgeSearchRequest
from src.knowledge.service import PolicyKnowledgeService
from src.rag.evaluation.contracts import load_format_parity_contract
from src.rag.evaluation.retrieval_rounds import (
    RecordingPolicyRetrievalEngine,
    RetrievalParityRunV1,
    build_knowledge_query,
    ordered_gold_questions,
    run_retrieval_parity,
)
from scripts.eval_rag_format_parity import (
    build_unavailable_result,
    parse_args,
    validate_provider_arguments,
)


MIGRATION = Path("src/db/migrations/versions/029_phase64_3_rag_eval_rounds.py")


def _identity(**overrides: object) -> EvaluationRoundIdentity:
    values: dict[str, object] = {
        "round_id": uuid4(),
        "tenant_id": FORMAT_PARITY_TENANT_ID,
        "owner_marker": FORMAT_PARITY_OWNER_MARKER,
        "run_token": uuid4(),
        "round_token": uuid4(),
        "round_format": "markdown",
        "state_version": 1,
        "next_document_index": 0,
    }
    values.update(overrides)
    return EvaluationRoundIdentity(**values)


def test_fixed_evaluation_identity_and_orm_constraints_are_exact() -> None:
    assert FORMAT_PARITY_TENANT_ID == UUID("64300000-0000-4000-8000-000000000001")
    assert FORMAT_PARITY_OWNER_MARKER == "moca.rag_format_parity.v1"
    assert FORMAT_PARITY_DOC_KEYS == (
        "eval_refund_eligibility_and_return",
        "eval_quality_compensation_and_approval",
        "eval_cross_border_and_digital_goods",
    )
    assert ROUND_FORMATS == ("markdown", "digital_pdf", "scanned_pdf")

    table = RagEvaluationRound.__table__
    assert {
        "tenant_id",
        "owner_marker",
        "run_token",
        "round_token",
        "round_format",
        "doc_keys_json",
        "state",
        "state_version",
        "expected_rollout_version",
        "next_document_index",
        "next_step",
        "attempt_doc_key",
        "expected_source_checksum",
        "reservation_at",
        "claimed_job_id",
        "lease_expires_at",
        "pre_state_proof_json",
        "post_state_proof_json",
        "head_mappings_json",
        "immutable_counts_json",
    } <= set(table.columns.keys())
    checks = "\n".join(str(constraint.sqltext) for constraint in table.constraints if hasattr(constraint, "sqltext"))
    assert str(FORMAT_PARITY_TENANT_ID) in checks
    assert FORMAT_PARITY_OWNER_MARKER in checks
    assert all(value in checks for value in (*ROUND_FORMATS, *FORMAT_PARITY_DOC_KEYS))
    assert "state_version > 0" in checks
    assert "next_document_index >= 0" in checks
    active_index = next(index for index in table.indexes if index.name == "uq_rag_evaluation_rounds_one_active_tenant")
    assert active_index.unique is True
    assert "completed" in str(active_index.dialect_options["postgresql"]["where"])
    assert "abandoned" in str(active_index.dialect_options["postgresql"]["where"])


def test_migration_is_chained_partial_unique_and_evaluation_only() -> None:
    source = MIGRATION.read_text(encoding="utf-8")
    assert 'down_revision: str | None = "028_phase64_2_memory_lifecycle"' in source
    assert 'op.create_table(\n        "rag_evaluation_rounds"' in source
    assert '"uq_rag_evaluation_rounds_one_active_tenant"' in source
    assert "postgresql_where" in source
    assert "_assert_downgrade_safe()" in source
    assert "refusing downgrade" in source
    assert 'op.drop_table("rag_evaluation_rounds")' in source
    assert "policy_document_versions" not in source
    assert "policy_chunk_versions" not in source
    assert "DROP TRIGGER" not in source
    assert "DROP FUNCTION" not in source


@pytest.mark.parametrize(
    ("overrides", "reason_code"),
    [
        ({"tenant_id": uuid4()}, "identity_mismatch"),
        ({"owner_marker": "other"}, "identity_mismatch"),
        ({"run_token": UUID(int=0)}, "identity_mismatch"),
        ({"round_token": UUID(int=0)}, "identity_mismatch"),
        ({"round_format": "docx"}, "identity_mismatch"),
        ({"state_version": 0}, "stale_state"),
        ({"next_document_index": 4}, "stale_progress"),
    ],
)
def test_wrong_identity_denies_with_one_generic_external_error(overrides: dict[str, object], reason_code: str) -> None:
    with pytest.raises(EvaluationIsolationError) as caught:
        _identity(**overrides)
    assert str(caught.value) == "evaluation isolation denied"
    assert caught.value.reason_code == reason_code


@pytest.mark.parametrize(
    ("projection", "expected"),
    [
        (AttemptProjection(), ProjectionState.RESERVATION_ONLY),
        (
            AttemptProjection(job_count=1, null_doc_job_count=1),
            ProjectionState.JOB_ONLY,
        ),
        (
            AttemptProjection(job_count=1, null_doc_job_count=1, failed_job_count=1),
            ProjectionState.FAILURE,
        ),
        (
            AttemptProjection(
                head_count=1,
                matching_head_count=1,
                block_count=2,
                chunk_count=3,
                immutable_document_count=1,
                immutable_chunk_count=3,
                canonical_binding_count=3,
                job_count=1,
                success_job_count=1,
            ),
            ProjectionState.EXACT_COMPLETE,
        ),
        (AttemptProjection(job_count=2, null_doc_job_count=2), ProjectionState.MALFORMED),
        (
            AttemptProjection(head_count=1, matching_head_count=0, job_count=1, success_job_count=1),
            ProjectionState.MALFORMED,
        ),
        (
            AttemptProjection(
                head_count=1,
                matching_head_count=1,
                block_count=1,
                chunk_count=0,
                job_count=1,
                success_job_count=1,
            ),
            ProjectionState.MALFORMED,
        ),
    ],
)
def test_commit_aware_projection_taxonomy(projection: AttemptProjection, expected: ProjectionState) -> None:
    assert classify_attempt_projection(projection) is expected


class _Rows:
    def __init__(self, values: list[object]) -> None:
        self._values = values

    def scalars(self) -> _Rows:
        return self

    def all(self) -> list[object]:
        return self._values


class _CaptureSession:
    def __init__(self, values: list[object] | None = None, rowcount: int = 1) -> None:
        self.values = values or []
        self.rowcount = rowcount
        self.statements: list[object] = []

    async def execute(self, statement: object) -> object:
        self.statements.append(statement)
        if statement.__class__.__name__ == "Delete":
            return type("DeleteResult", (), {"rowcount": self.rowcount})()
        return _Rows(self.values)


class _SequenceResult(_Rows):
    def __init__(self, values: list[object] | None = None, *, scalar: int | None = None) -> None:
        super().__init__(values or [])
        self._scalar = scalar

    def scalar_one(self) -> int:
        assert self._scalar is not None
        return self._scalar


class _SequenceSession:
    def __init__(self, results: list[_SequenceResult]) -> None:
        self.results = results
        self.statements: list[object] = []

    async def execute(self, statement: object) -> _SequenceResult:
        self.statements.append(statement)
        return self.results.pop(0)


def _sql(statement: object) -> str:
    return str(statement.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": False}))


@pytest.mark.asyncio
async def test_null_doc_job_candidate_lock_and_delete_use_full_exact_predicates() -> None:
    session = _CaptureSession()
    repo = RagIngestionJobRepository(session)  # type: ignore[arg-type]
    reserved_at = datetime(2026, 8, 10, tzinfo=UTC)
    checksum = "a" * 64
    candidates = await repo.lock_evaluation_attempt_candidates(
        tenant_id=FORMAT_PARITY_TENANT_ID,
        doc_key=FORMAT_PARITY_DOC_KEYS[0],
        source_checksum=checksum,
        reserved_at=reserved_at,
    )
    assert candidates == []
    select_sql = _sql(session.statements[-1])
    assert "rag_ingestion_jobs.tenant_id =" in select_sql
    assert "rag_ingestion_jobs.doc_key =" in select_sql
    assert "rag_ingestion_jobs.source_checksum =" in select_sql
    assert "rag_ingestion_jobs.created_at >=" in select_sql
    assert "rag_ingestion_jobs.doc_id IS NULL" in select_sql
    assert "FOR UPDATE" in select_sql
    assert "LIMIT" in select_sql
    select_params = session.statements[-1].compile(dialect=postgresql.dialect()).params
    assert f"sha256:{checksum}" in select_params.values()
    assert checksum not in select_params.values()

    job_id = uuid4()
    deleted = await repo.delete_exact_evaluation_attempt(
        job_id=job_id,
        tenant_id=FORMAT_PARITY_TENANT_ID,
        doc_key=FORMAT_PARITY_DOC_KEYS[0],
        source_checksum=checksum,
    )
    assert deleted == 1
    delete_sql = _sql(session.statements[-1])
    for column in ("id", "tenant_id", "doc_key", "source_checksum"):
        assert f"rag_ingestion_jobs.{column} =" in delete_sql
    assert "doc_key LIKE" not in delete_sql


@pytest.mark.asyncio
async def test_manifest_checksum_is_canonicalized_for_exact_lookup_classification_and_cleanup() -> None:
    owner_checksum = "a" * 64
    production_checksum = f"sha256:{owner_checksum}"
    reserved_at = datetime(2026, 8, 10, tzinfo=UTC)
    document_id = uuid4()
    job_id = uuid4()
    chunk_id = "eval-chunk-1"
    session = _SequenceSession(
        [
            _SequenceResult(
                [
                    SimpleNamespace(
                        id=document_id,
                        source_checksum=production_checksum,
                        version=1,
                    )
                ]
            ),
            _SequenceResult(
                [
                    SimpleNamespace(
                        id=job_id,
                        doc_id=document_id,
                        source_checksum=production_checksum,
                        status="success",
                    )
                ]
            ),
            _SequenceResult([SimpleNamespace(id=uuid4())]),
            _SequenceResult([SimpleNamespace(chunk_id=chunk_id)]),
            _SequenceResult([SimpleNamespace(id=uuid4())]),
            _SequenceResult([SimpleNamespace(chunk_id=chunk_id)]),
            _SequenceResult(scalar=1),
            _SequenceResult(scalar=1),
        ]
    )
    repo = RagEvaluationRoundRepository(session)  # type: ignore[arg-type]
    inspection = await repo._inspect_locked(  # noqa: SLF001 - exact durable projection contract
        SimpleNamespace(
            tenant_id=FORMAT_PARITY_TENANT_ID,
            attempt_doc_key=FORMAT_PARITY_DOC_KEYS[0],
            expected_source_checksum=owner_checksum,
            reservation_at=reserved_at,
        )
    )

    assert inspection.state is ProjectionState.EXACT_COMPLETE
    assert inspection.projection.matching_head_count == 1
    assert inspection.projection.job_count == 1
    lookup_params = session.statements[1].compile(dialect=postgresql.dialect()).params
    assert production_checksum in lookup_params.values()
    assert owner_checksum not in lookup_params.values()

    delete_session = _CaptureSession()
    deleted = await RagIngestionJobRepository(delete_session).delete_exact_evaluation_attempt(  # type: ignore[arg-type]
        job_id=job_id,
        tenant_id=FORMAT_PARITY_TENANT_ID,
        doc_key=FORMAT_PARITY_DOC_KEYS[0],
        source_checksum=owner_checksum,
    )
    assert deleted == 1
    delete_params = delete_session.statements[-1].compile(dialect=postgresql.dialect()).params
    assert production_checksum in delete_params.values()
    assert owner_checksum not in delete_params.values()

    with pytest.raises(ValueError, match="evaluation_source_checksum_invalid"):
        await RagIngestionJobRepository(_CaptureSession()).lock_evaluation_attempt_candidates(  # type: ignore[arg-type]
            tenant_id=FORMAT_PARITY_TENANT_ID,
            doc_key=FORMAT_PARITY_DOC_KEYS[0],
            source_checksum=production_checksum,
            reserved_at=reserved_at,
        )


def test_repository_source_has_no_broad_or_immutable_delete_path() -> None:
    source = inspect.getsource(RagEvaluationRoundRepository)
    lowered = source.lower()
    assert "truncate" not in lowered
    assert "startswith" not in lowered
    assert "like(" not in lowered
    assert "delete(policydocument)" not in lowered
    assert "delete(policydocumentversion)" not in lowered
    assert "delete(policychunkversion)" not in lowered
    assert "update(policydocumentversion)" not in lowered
    assert "update(policychunkversion)" not in lowered


def _dataset():
    return load_format_parity_contract(
        Path("evaluation/rag_sources/format_parity_manifest.jsonl"),
        Path("evaluation/golden/rag_format_parity_gold.json"),
        repository_root=Path.cwd(),
    )


def test_gold_question_order_is_format_independent_and_complete() -> None:
    questions = ordered_gold_questions(_dataset())
    expected = tuple(
        (policy.doc_key, case.case_id, case.question) for policy in _dataset().policies for case in policy.gold.cases
    )
    assert questions == expected
    assert len(questions) == 18


def test_real_request_and_context_are_bound_to_fixed_tenant() -> None:
    request, context = build_knowledge_query(
        question="退款资格是什么？",
        generated_at="2026-08-10T00:00:00Z",
    )
    assert isinstance(request, KnowledgeSearchRequest)
    assert isinstance(context, KnowledgeContext)
    assert request.filters.tenant_id == str(FORMAT_PARITY_TENANT_ID)
    assert context.tenant_id == str(FORMAT_PARITY_TENANT_ID)
    assert request.query == "退款资格是什么？"


class _RealEngineSpy:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    async def retrieve_run(self, **kwargs: object) -> PolicyRetrievalRun:
        self.calls.append(kwargs)
        return PolicyRetrievalRun(
            status="no_evidence",
            hits=[],
            evidence_refs=[],
            best_score=0.0,
            original_query=str(kwargs["query"]),
            fallback_reason="no_candidates",
        )


@pytest.mark.asyncio
async def test_recording_delegate_forwards_the_single_service_triggered_retrieval() -> None:
    engine = _RealEngineSpy()
    delegate = RecordingPolicyRetrievalEngine(engine)  # type: ignore[arg-type]
    service = PolicyKnowledgeService(delegate)
    request, context = build_knowledge_query(
        question="退款资格是什么？",
        generated_at="2026-08-10T00:00:00Z",
    )
    result = await service.search(request, context)
    recording = delegate.take_recording(expected_query=request.query)

    assert result.status == "no_evidence"
    assert len(engine.calls) == 1
    assert recording.original_query == request.query
    assert recording.fallback_reason == "no_candidates"
    with pytest.raises(EvaluationIsolationError, match="evaluation isolation denied"):
        delegate.take_recording(expected_query=request.query)


def test_provider_runtime_owns_real_service_boundaries_and_contract_mode_is_ineligible() -> None:
    source = inspect.getsource(run_retrieval_parity)
    assert "IngestionService(" in source
    assert "PolicyRetrievalEngine(" in source
    assert "PolicyKnowledgeService(" in source
    assert ".search(" in source
    assert "retrieve_run(" not in source
    contract = RetrievalParityRunV1(
        mode="contract_test",
        baseline_eligible=False,
        outcome="completed_quality_fail",
        generated_at="2026-08-10T00:00:00Z",
        tenant_id=str(FORMAT_PARITY_TENANT_ID),
        owner_marker=FORMAT_PARITY_OWNER_MARKER,
        run_token=str(uuid4()),
        manifest_hash="a" * 64,
        gold_hash="b" * 64,
        baseline_identity="c" * 64,
        rounds=(),
        prerequisites=(),
    )
    assert contract.baseline_eligible is False
    with pytest.raises(ValueError):
        contract.model_copy(update={"baseline_eligible": True}).model_validate(
            contract.model_copy(update={"baseline_eligible": True}).model_dump()
        )


def _provider_argv(**overrides: str) -> list[str]:
    values = {
        "mode": "provider",
        "manifest": "evaluation/rag_sources/format_parity_manifest.jsonl",
        "gold": "evaluation/golden/rag_format_parity_gold.json",
        "tenant_id": str(FORMAT_PARITY_TENANT_ID),
        "owner_marker": FORMAT_PARITY_OWNER_MARKER,
        "run_token": str(uuid4()),
        "expected_rollout_version": "1",
        "output": "/tmp/rag-format-parity.json",
        "generated_at": "2026-08-10T00:00:00Z",
    }
    values.update(overrides)
    return [
        "--mode",
        values["mode"],
        "--manifest",
        values["manifest"],
        "--gold",
        values["gold"],
        "--tenant-id",
        values["tenant_id"],
        "--owner-marker",
        values["owner_marker"],
        "--run-token",
        values["run_token"],
        "--expected-rollout-version",
        values["expected_rollout_version"],
        "--output",
        values["output"],
        "--generated-at",
        values["generated_at"],
    ]


@pytest.mark.parametrize(
    "overrides",
    [
        {"tenant_id": str(uuid4())},
        {"owner_marker": "wrong-owner"},
        {"run_token": "not-a-uuid"},
        {"run_token": str(UUID(int=0))},
        {"expected_rollout_version": "0"},
    ],
)
def test_cli_rejects_wrong_provider_identity_before_mutation(overrides: dict[str, str]) -> None:
    args = parse_args(_provider_argv(**overrides))
    with pytest.raises(EvaluationIsolationError):
        validate_provider_arguments(args)


def test_cli_is_provider_only_and_has_no_fake_or_reset_switch() -> None:
    args = parse_args(_provider_argv())
    validate_provider_arguments(args)
    assert args.mode == "provider"
    with pytest.raises(SystemExit):
        parse_args([*_provider_argv(), "--fake"])
    source = Path("scripts/eval_rag_format_parity.py").read_text(encoding="utf-8").lower()
    for forbidden in ("first active", "truncate", "delete.*prefix", "--fake", "reset-all"):
        assert forbidden not in source


def test_missing_prerequisites_are_safe_unavailable_not_zero_quality() -> None:
    dataset = _dataset()
    result = build_unavailable_result(
        dataset=dataset,
        run_token=uuid4(),
        generated_at="2026-08-10T00:00:00Z",
        missing=("database_schema", "embedding_provider", "ocr_traineddata"),
    )
    payload = result.model_dump(mode="json")
    serialized = result.model_dump_json()
    assert payload["outcome"] == "unavailable_prerequisite"
    assert payload["baseline_eligible"] is False
    assert payload["rounds"] == []
    assert "metrics" not in payload
    assert "score" not in payload
    assert "pass" not in payload
    for forbidden in (
        "postgresql+asyncpg://",
        "dashscope_api_key",
        "api_key",
        "traceback",
        "/users/",
        "/private/",
        "raw_payload",
    ):
        assert forbidden not in serialized.lower()
