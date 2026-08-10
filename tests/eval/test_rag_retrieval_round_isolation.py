from __future__ import annotations

import inspect
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from sqlalchemy.dialects import postgresql

import src.rag.evaluation.retrieval_rounds as retrieval_rounds_module
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


@pytest.mark.asyncio
async def test_failed_scanned_quality_transition_deletes_proves_then_advances_cas(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner = _identity(round_format="scanned_pdf", next_document_index=2)
    job_id = uuid4()
    checksum = "b" * 64
    reserved_at = datetime(2026, 8, 10, tzinfo=UTC)
    row = SimpleNamespace(
        tenant_id=FORMAT_PARITY_TENANT_ID,
        attempt_doc_key=FORMAT_PARITY_DOC_KEYS[2],
        expected_source_checksum=checksum,
        reservation_at=reserved_at,
        claimed_job_id=job_id,
        immutable_counts_json={"document_versions": 3, "chunk_versions": 13},
    )
    failure = SimpleNamespace(
        state=ProjectionState.FAILURE,
        job_id=job_id,
        job_error_code="malformed_source",
        projection=AttemptProjection(job_count=1, failed_job_count=1),
        immutable_counts={"document_versions": 3, "chunk_versions": 13},
    )
    empty = SimpleNamespace(
        state=ProjectionState.RESERVATION_ONLY,
        job_id=None,
        projection=AttemptProjection(),
        immutable_counts={"document_versions": 3, "chunk_versions": 13},
    )
    inspections = iter((failure, empty))
    events: list[object] = []
    cas_values: dict[str, object] = {}
    repo = RagEvaluationRoundRepository(SimpleNamespace())  # type: ignore[arg-type]

    async def lock_owned(*args: object, **kwargs: object) -> object:
        events.append(("lock", kwargs["allowed_states"]))
        return row

    async def inspect_locked(*args: object) -> object:
        inspection = next(inspections)
        events.append(("inspect", inspection.state))
        return inspection

    async def delete_exact_evaluation_attempt(**kwargs: object) -> int:
        events.append(("delete", kwargs))
        return 1

    async def cas(*args: object, **kwargs: object) -> EvaluationRoundIdentity:
        del args
        cas_values.update(kwargs)
        events.append(("cas", kwargs["next_document_index"]))
        return _identity(
            round_id=owner.round_id,
            run_token=owner.run_token,
            round_token=owner.round_token,
            round_format="scanned_pdf",
            next_document_index=3,
            state_version=2,
        )

    monkeypatch.setattr(repo, "lock_owned", lock_owned)
    monkeypatch.setattr(repo, "_inspect_locked", inspect_locked)
    monkeypatch.setattr(repo.job_repo, "delete_exact_evaluation_attempt", delete_exact_evaluation_attempt)
    monkeypatch.setattr(repo, "_cas", cas)

    advanced = await repo.advance_exact_failed_quality(owner, error_code="malformed_source")

    assert advanced.next_document_index == 3
    assert events == [
        ("lock", frozenset({"ingesting"})),
        ("inspect", ProjectionState.FAILURE),
        (
            "delete",
            {
                "job_id": job_id,
                "tenant_id": FORMAT_PARITY_TENANT_ID,
                "doc_key": FORMAT_PARITY_DOC_KEYS[2],
                "source_checksum": checksum,
            },
        ),
        ("inspect", ProjectionState.RESERVATION_ONLY),
        ("cas", 3),
    ]
    assert cas_values == {
        "state": "cleaning",
        "next_step": "cleanup",
        "next_document_index": 3,
        "claimed_job_id": None,
        "attempt_doc_key": None,
        "expected_source_checksum": None,
        "reservation_at": None,
        "immutable_counts_json": {"document_versions": 3, "chunk_versions": 13},
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("round_format", "error_code"),
    [("markdown", "malformed_source"), ("scanned_pdf", "embedding_failed")],
)
async def test_failed_quality_transition_rejects_uncontrolled_format_or_error(
    round_format: str,
    error_code: str,
) -> None:
    repo = RagEvaluationRoundRepository(SimpleNamespace())  # type: ignore[arg-type]
    with pytest.raises(EvaluationIsolationError) as caught:
        await repo.advance_exact_failed_quality(
            _identity(round_format=round_format),
            error_code=error_code,
        )
    assert caught.value.reason_code == "quality_failure_not_allowed"


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


class _TrackedTransaction:
    def __init__(self, session: _TransactionTrackingSession) -> None:
        self.session = session

    async def __aenter__(self) -> None:
        if self.session.active:
            raise RuntimeError("transaction scope conflict")
        self.session.active = True
        self.session.begin_count += 1

    async def __aexit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.session.active = False
        if exc_type is None:
            self.session.commit_count += 1
        else:
            self.session.rollback_count += 1


class _TransactionTrackingSession:
    def __init__(self) -> None:
        self.active = False
        self.begin_count = 0
        self.commit_count = 0
        self.rollback_count = 0
        self.implicit_query_count = 0

    def begin(self) -> _TrackedTransaction:
        return _TrackedTransaction(self)

    def mark_service_query(self) -> None:
        self.implicit_query_count += 1
        if not self.active:
            self.active = True


class _TransactionalEngineSpy:
    mismatch_recording = False
    calls = 0

    def __init__(self, session: _TransactionTrackingSession, *, embedder: object) -> None:
        del embedder
        self.session = session

    async def retrieve_run(self, **kwargs: object) -> PolicyRetrievalRun:
        type(self).calls += 1
        self.session.mark_service_query()
        query = str(kwargs["query"])
        return PolicyRetrievalRun(
            status="no_evidence",
            hits=[],
            evidence_refs=[],
            best_score=0.0,
            original_query="unexpected query" if type(self).mismatch_recording else query,
            fallback_reason="no_candidates",
        )


class _TransactionRoundRepository:
    cleanup_calls = 0

    def __init__(self, session: _TransactionTrackingSession) -> None:
        self.session = session

    async def read_progress(self, owner: EvaluationRoundIdentity) -> object:
        return SimpleNamespace(state="retrieving", has_attempt_reservation=False)

    async def prove_retrieval_ready(self, owner: EvaluationRoundIdentity) -> EvaluationRoundIdentity:
        return owner

    async def cleanup_current_projection(
        self,
        owner: EvaluationRoundIdentity,
        *,
        terminal_state: str,
        failure_code: str | None = None,
    ) -> EvaluationRoundIdentity:
        del terminal_state, failure_code
        assert self.session.active
        type(self).cleanup_calls += 1
        return owner

    async def create_round(
        self,
        *,
        run_token: UUID,
        round_token: UUID,
        round_format: str,
        lease_expires_at: datetime,
        expected_rollout_version: int,
    ) -> EvaluationRoundIdentity:
        del lease_expires_at
        return EvaluationRoundIdentity(
            round_id=uuid4(),
            tenant_id=FORMAT_PARITY_TENANT_ID,
            owner_marker=FORMAT_PARITY_OWNER_MARKER,
            run_token=run_token,
            round_token=round_token,
            round_format=round_format,
            state_version=1,
            next_document_index=3,
            expected_rollout_version=expected_rollout_version,
        )


@pytest.fixture
def transaction_runtime(monkeypatch: pytest.MonkeyPatch) -> _TransactionTrackingSession:
    _TransactionalEngineSpy.calls = 0
    _TransactionalEngineSpy.mismatch_recording = False
    _TransactionRoundRepository.cleanup_calls = 0
    session = _TransactionTrackingSession()
    monkeypatch.setattr(retrieval_rounds_module, "PolicyRetrievalEngine", _TransactionalEngineSpy)
    monkeypatch.setattr(retrieval_rounds_module, "RagEvaluationRoundRepository", _TransactionRoundRepository)
    monkeypatch.setattr(retrieval_rounds_module, "IngestionService", lambda *args, **kwargs: object())
    return session


@pytest.mark.asyncio
async def test_each_service_search_closes_its_short_transaction_before_cleanup(
    transaction_runtime: _TransactionTrackingSession,
) -> None:
    owner = _identity(next_document_index=3)
    result = await run_retrieval_parity(
        _dataset(),
        session=transaction_runtime,  # type: ignore[arg-type]
        embedder=object(),  # type: ignore[arg-type]
        owner=owner,
        generated_at="2026-08-10T00:00:00Z",
    )

    assert result.outcome == "completed_quality_fail"
    assert transaction_runtime.active is False
    assert transaction_runtime.implicit_query_count == 54
    assert _TransactionalEngineSpy.calls == 54
    assert _TransactionRoundRepository.cleanup_calls == 3
    assert transaction_runtime.commit_count == transaction_runtime.begin_count
    assert transaction_runtime.rollback_count == 0


@pytest.mark.asyncio
async def test_recording_failure_rolls_back_search_transaction_and_preserves_reason_for_cleanup(
    transaction_runtime: _TransactionTrackingSession,
) -> None:
    _TransactionalEngineSpy.mismatch_recording = True
    result = await run_retrieval_parity(
        _dataset(),
        session=transaction_runtime,  # type: ignore[arg-type]
        embedder=object(),  # type: ignore[arg-type]
        owner=_identity(next_document_index=3),
        generated_at="2026-08-10T00:00:00Z",
    )

    assert result.outcome == "execution_error"
    assert result.rounds[0].reason_code == "retrieval_recording_mismatch"
    assert transaction_runtime.active is False
    assert transaction_runtime.rollback_count == 1
    assert _TransactionalEngineSpy.calls == 1
    assert _TransactionRoundRepository.cleanup_calls == 1


class _ScannedFailureIngestionService:
    error_code = "malformed_source"
    calls: list[str] = []

    def __init__(self, *args: object, **kwargs: object) -> None:
        del args, kwargs

    async def ingest_document(self, source_path: Path, doc_meta: dict[str, object], **kwargs: object) -> object:
        del source_path, kwargs
        doc_key = str(doc_meta["doc_key"])
        type(self).calls.append(doc_key)
        return SimpleNamespace(status="failed", error_code=type(self).error_code)


class _ScannedFailureRoundRepository(_TransactionRoundRepository):
    quality_advance_calls = 0
    retry_calls = 0

    async def read_progress(self, owner: EvaluationRoundIdentity) -> object:
        if owner.round_format == "scanned_pdf" and owner.next_document_index < 3:
            return SimpleNamespace(state="claimed", has_attempt_reservation=False)
        return await super().read_progress(owner)

    async def prove_compatible_pre_state(self, owner: EvaluationRoundIdentity) -> EvaluationRoundIdentity:
        return owner

    async def reserve_document(self, owner: EvaluationRoundIdentity, **kwargs: object) -> EvaluationRoundIdentity:
        del kwargs
        return owner

    async def inspect_attempt(self, owner: EvaluationRoundIdentity) -> object:
        del owner
        return SimpleNamespace(state=ProjectionState.FAILURE)

    async def claim_attempt_job(
        self,
        owner: EvaluationRoundIdentity,
        *,
        require_null_document: bool,
    ) -> EvaluationRoundIdentity:
        assert require_null_document is False
        return owner

    async def retry_attempt(self, owner: EvaluationRoundIdentity) -> EvaluationRoundIdentity:
        type(self).retry_calls += 1
        return owner

    async def advance_exact_failed_quality(
        self,
        owner: EvaluationRoundIdentity,
        *,
        error_code: str,
    ) -> EvaluationRoundIdentity:
        assert owner.round_format == "scanned_pdf"
        assert error_code == "malformed_source"
        type(self).quality_advance_calls += 1
        return _identity(
            round_id=owner.round_id,
            run_token=owner.run_token,
            round_token=owner.round_token,
            round_format=owner.round_format,
            next_document_index=owner.next_document_index + 1,
            state_version=owner.state_version + 1,
        )

    async def create_round(
        self,
        *,
        run_token: UUID,
        round_token: UUID,
        round_format: str,
        lease_expires_at: datetime,
        expected_rollout_version: int,
    ) -> EvaluationRoundIdentity:
        del lease_expires_at
        return EvaluationRoundIdentity(
            round_id=uuid4(),
            tenant_id=FORMAT_PARITY_TENANT_ID,
            owner_marker=FORMAT_PARITY_OWNER_MARKER,
            run_token=run_token,
            round_token=round_token,
            round_format=round_format,
            state_version=1,
            next_document_index=0 if round_format == "scanned_pdf" else 3,
            expected_rollout_version=expected_rollout_version,
        )


class _RecoveredReservationRoundRepository(_ScannedFailureRoundRepository):
    inspections: list[ProjectionState] = []

    async def inspect_attempt(self, owner: EvaluationRoundIdentity) -> object:
        del owner
        return SimpleNamespace(state=type(self).inspections.pop(0))


async def _run_scanned_failure(
    monkeypatch: pytest.MonkeyPatch,
    *,
    error_code: str,
) -> tuple[RetrievalParityRunV1, _TransactionTrackingSession]:
    _TransactionalEngineSpy.calls = 0
    _TransactionalEngineSpy.mismatch_recording = False
    _ScannedFailureIngestionService.error_code = error_code
    _ScannedFailureIngestionService.calls = []
    _ScannedFailureRoundRepository.cleanup_calls = 0
    _ScannedFailureRoundRepository.quality_advance_calls = 0
    _ScannedFailureRoundRepository.retry_calls = 0
    session = _TransactionTrackingSession()
    monkeypatch.setattr(retrieval_rounds_module, "PolicyRetrievalEngine", _TransactionalEngineSpy)
    monkeypatch.setattr(retrieval_rounds_module, "RagEvaluationRoundRepository", _ScannedFailureRoundRepository)
    monkeypatch.setattr(retrieval_rounds_module, "IngestionService", _ScannedFailureIngestionService)
    result = await run_retrieval_parity(
        _dataset(),
        session=session,  # type: ignore[arg-type]
        embedder=object(),  # type: ignore[arg-type]
        owner=_identity(next_document_index=3),
        generated_at="2026-08-10T00:00:00Z",
    )
    return result, session


@pytest.mark.asyncio
async def test_recovered_reservation_requires_two_real_malformed_reports_before_quality_advance() -> None:
    _ScannedFailureIngestionService.error_code = "malformed_source"
    _ScannedFailureIngestionService.calls = []
    _RecoveredReservationRoundRepository.inspections = [
        ProjectionState.RESERVATION_ONLY,
        ProjectionState.FAILURE,
        ProjectionState.FAILURE,
    ]
    _RecoveredReservationRoundRepository.quality_advance_calls = 0
    _RecoveredReservationRoundRepository.retry_calls = 0
    session = _TransactionTrackingSession()
    repo = _RecoveredReservationRoundRepository(session)
    owner, observation, fatal_reason = await retrieval_rounds_module._resolve_ingestion_attempt(  # noqa: SLF001
        session=session,  # type: ignore[arg-type]
        round_repo=repo,  # type: ignore[arg-type]
        ingestion_service=_ScannedFailureIngestionService(),  # type: ignore[arg-type]
        owner=_identity(round_format="scanned_pdf"),
        round_format="scanned_pdf",
        source_path=Path("evaluation/scanned-placeholder.pdf"),
        source_checksum="c" * 64,
        doc_meta={"doc_key": FORMAT_PARITY_DOC_KEYS[0]},
        first_report=None,
    )

    assert owner.next_document_index == 1
    assert observation.status == "failed"
    assert observation.error_code == "malformed_source"
    assert fatal_reason is None
    assert _ScannedFailureIngestionService.calls == [FORMAT_PARITY_DOC_KEYS[0]] * 2
    assert _RecoveredReservationRoundRepository.retry_calls == 1
    assert _RecoveredReservationRoundRepository.quality_advance_calls == 1


@pytest.mark.asyncio
async def test_three_scanned_malformed_sources_are_quality_failure_without_retrieval(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result, session = await _run_scanned_failure(monkeypatch, error_code="malformed_source")

    assert result.outcome == "completed_quality_fail"
    assert result.baseline_eligible is True
    assert [item.round_format for item in result.rounds] == ["markdown", "digital_pdf", "scanned_pdf"]
    scanned = result.rounds[2]
    assert scanned.outcome == "completed_quality_fail"
    assert scanned.cases == ()
    assert scanned.exactly_three_current_proved is False
    assert scanned.post_state_proved is True
    assert scanned.immutable_history_preserved is True
    assert [item.status for item in scanned.ingestions] == ["failed", "failed", "failed"]
    assert [item.error_code for item in scanned.ingestions] == ["malformed_source"] * 3
    assert Counter(_ScannedFailureIngestionService.calls) == Counter({doc_key: 2 for doc_key in FORMAT_PARITY_DOC_KEYS})
    assert _ScannedFailureRoundRepository.quality_advance_calls == 3
    assert _TransactionalEngineSpy.calls == 36
    assert session.active is False


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error_code",
    ["embedding_count_mismatch", "db_write_failed", "job_trace_unavailable", "unexpected_provider_failure"],
)
async def test_other_second_ingestion_error_remains_execution_error_with_stable_reason(
    monkeypatch: pytest.MonkeyPatch,
    error_code: str,
) -> None:
    result, session = await _run_scanned_failure(monkeypatch, error_code=error_code)

    assert result.outcome == "execution_error"
    assert result.baseline_eligible is False
    assert len(result.rounds) == 3
    scanned = result.rounds[2]
    assert scanned.outcome == "execution_error"
    assert scanned.reason_code == f"ingestion_failed:{error_code}"
    assert scanned.cases == ()
    assert scanned.post_state_proved is True
    assert scanned.immutable_history_preserved is True
    assert _ScannedFailureRoundRepository.quality_advance_calls == 0
    assert _ScannedFailureIngestionService.calls == [FORMAT_PARITY_DOC_KEYS[0]] * 2
    assert _TransactionalEngineSpy.calls == 36
    assert session.active is False


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
