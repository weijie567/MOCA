from __future__ import annotations

import inspect
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

import pytest
from sqlalchemy.dialects import postgresql

import src.rag.evaluation.retrieval_rounds as retrieval_rounds_module
import src.repositories.rag_evaluation_round_repo as round_repo_module
import scripts.eval_rag_format_parity as format_parity_cli
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
    validate_run_sequence,
)
from src.repositories.rag_ingestion_job_repo import RagIngestionJobRepository
from src.knowledge.provenance import EvidenceProvenance, SourceLocator
from src.knowledge.retrieval import PolicyRetrievalHit, PolicyRetrievalRun
from src.knowledge.schemas import EvidenceRefV1, KnowledgeContext, KnowledgeSearchRequest
from src.knowledge.service import PolicyKnowledgeService
from src.knowledge.text_hash import evidence_text_hash
from src.rag.evaluation.contracts import FormatParityContractError, load_format_parity_contract
from src.rag.evaluation.retrieval_rounds import (
    RecordingPolicyRetrievalEngine,
    RetrievalParityRunV1,
    RetrievalRoundResultV1,
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


def _sequence_row(
    *,
    run_token: UUID,
    round_format: str,
    state: str,
    expected_rollout_version: int = 2,
) -> SimpleNamespace:
    round_token = uuid5(NAMESPACE_URL, f"{run_token}:{round_format}")
    terminal = state == "completed"
    round_result = RetrievalRoundResultV1(
        round_format=round_format,  # type: ignore[arg-type]
        round_token=str(round_token),
        outcome="completed_pass",
        pre_state_proved=True,
        exactly_three_current_proved=True,
        post_state_proved=True,
        immutable_history_preserved=True,
    ).model_dump(mode="json")
    return SimpleNamespace(
        id=uuid4(),
        tenant_id=FORMAT_PARITY_TENANT_ID,
        owner_marker=FORMAT_PARITY_OWNER_MARKER,
        run_token=run_token,
        round_token=round_token,
        round_format=round_format,
        doc_keys_json=list(FORMAT_PARITY_DOC_KEYS),
        state=state,
        state_version=7,
        expected_rollout_version=expected_rollout_version,
        next_document_index=3 if terminal else 0,
        next_step="done" if terminal else "preflight",
        attempt_doc_key=None,
        expected_source_checksum=None,
        reservation_at=None,
        claimed_job_id=None,
        lease_expires_at=datetime.now(UTC) + timedelta(hours=1),
        post_state_proof_json=(
            {
                "current": {"documents": 3, "blocks": 0, "chunks": 0, "jobs": 0},
                "head_keys": list(FORMAT_PARITY_DOC_KEYS),
                "round_result": round_result,
            }
            if terminal
            else {}
        ),
        failure_code=None,
        terminal_at=datetime.now(UTC) if terminal else None,
    )


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


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("completed_formats", "active_format", "expected_format", "expected_create_count"),
    [
        (("markdown",), None, "digital_pdf", 1),
        (("markdown",), "digital_pdf", "digital_pdf", 0),
        (("markdown", "digital_pdf"), None, "scanned_pdf", 1),
        (("markdown", "digital_pdf"), "scanned_pdf", "scanned_pdf", 0),
    ],
)
async def test_same_token_resume_creates_only_first_missing_round_or_returns_any_active_format(
    monkeypatch: pytest.MonkeyPatch,
    completed_formats: tuple[str, ...],
    active_format: str | None,
    expected_format: str,
    expected_create_count: int,
) -> None:
    run_token = UUID("64300000-0000-4000-8000-000000000099")
    rows = [
        _sequence_row(run_token=run_token, round_format=round_format, state="completed")
        for round_format in completed_formats
    ]
    if active_format is not None:
        rows.append(_sequence_row(run_token=run_token, round_format=active_format, state="claimed"))

    class _RunRepository:
        create_calls: list[dict[str, object]] = []

        def __init__(self, session: object) -> None:
            del session

        async def lock_run_rows(self, requested_token: UUID) -> list[SimpleNamespace]:
            assert requested_token == run_token
            return rows

        async def create_round(self, **kwargs: object) -> EvaluationRoundIdentity:
            type(self).create_calls.append(kwargs)
            return _identity(
                run_token=run_token,
                round_token=kwargs["round_token"],
                round_format=kwargs["round_format"],
                expected_rollout_version=2,
            )

    _RunRepository.create_calls = []
    monkeypatch.setattr(format_parity_cli, "RagEvaluationRoundRepository", _RunRepository)
    owner = await format_parity_cli._claim_or_resume(
        SimpleNamespace(),  # type: ignore[arg-type]
        run_token=run_token,
        expected_rollout_version=2,
    )

    assert owner.round_format == expected_format
    assert owner.round_token == uuid5(NAMESPACE_URL, f"{run_token}:{expected_format}")
    assert len(_RunRepository.create_calls) == expected_create_count
    sequence = validate_run_sequence(
        rows,
        run_token=run_token,
        expected_rollout_version=2,
        now=datetime.now(UTC),
    )
    assert tuple(result["round_format"] for result in sequence.completed_results) == completed_formats


@pytest.mark.parametrize("drift", ["run_token", "tenant_id", "round_token", "format_gap"])
def test_run_sequence_rejects_cross_scope_and_deterministic_order_drift(drift: str) -> None:
    run_token = UUID("64300000-0000-4000-8000-000000000099")
    row = _sequence_row(run_token=run_token, round_format="markdown", state="claimed")
    if drift == "run_token":
        row.run_token = uuid4()
    elif drift == "tenant_id":
        row.tenant_id = uuid4()
    elif drift == "round_token":
        row.round_token = uuid4()
    else:
        row.round_format = "digital_pdf"

    with pytest.raises(EvaluationIsolationError):
        validate_run_sequence(
            [row],
            run_token=run_token,
            expected_rollout_version=2,
            now=datetime.now(UTC),
        )


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
async def test_run_row_lock_is_fixed_tenant_exact_token_and_denies_other_active_run() -> None:
    run_token = UUID("64300000-0000-4000-8000-000000000099")
    session = _SequenceSession([_SequenceResult([]), _SequenceResult([])])
    repo = RagEvaluationRoundRepository(session)  # type: ignore[arg-type]

    assert await repo.lock_run_rows(run_token) == []
    active_sql = _sql(session.statements[0])
    exact_sql = _sql(session.statements[1])
    assert "rag_evaluation_rounds.tenant_id =" in active_sql
    assert "rag_evaluation_rounds.state NOT IN" in active_sql
    assert "FOR UPDATE" in active_sql
    assert "rag_evaluation_rounds.tenant_id =" in exact_sql
    assert "rag_evaluation_rounds.run_token =" in exact_sql
    assert "FOR UPDATE" in exact_sql
    exact_params = session.statements[1].compile(dialect=postgresql.dialect()).params
    assert run_token in exact_params.values()

    other_run = SimpleNamespace(run_token=uuid4())
    conflicting = RagEvaluationRoundRepository(  # type: ignore[arg-type]
        _SequenceSession([_SequenceResult([other_run])])
    )
    with pytest.raises(EvaluationIsolationError) as caught:
        await conflicting.lock_run_rows(run_token)
    assert caught.value.reason_code == "active_round_mismatch"


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
    assert inspection.head_mapping == {
        FORMAT_PARITY_DOC_KEYS[0]: {
            "head_id": str(document_id),
            "source_checksum": production_checksum,
            "block_count": 1,
            "chunk_count": 1,
            "canonical_binding_count": 1,
        }
    }
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
@pytest.mark.parametrize(
    ("drift_field", "drift_value"),
    [
        ("head_id", str(uuid4())),
        ("source_checksum", "sha256:" + "c" * 64),
        ("block_count", 2),
        ("chunk_count", 2),
        ("canonical_binding_count", 0),
    ],
)
async def test_cleanup_rejects_replacement_or_mixed_projection_before_any_delete(
    monkeypatch: pytest.MonkeyPatch,
    drift_field: str,
    drift_value: object,
) -> None:
    owner = _identity(next_document_index=3)
    head = SimpleNamespace(
        id=uuid4(),
        doc_key=FORMAT_PARITY_DOC_KEYS[0],
        source_checksum="sha256:" + "a" * 64,
        version=1,
    )
    recorded = {
        "head_id": str(head.id),
        "source_checksum": head.source_checksum,
        "block_count": 1,
        "chunk_count": 1,
        "canonical_binding_count": 1,
    }
    actual = dict(recorded)
    actual[drift_field] = drift_value
    row = SimpleNamespace(
        head_mappings_json={head.doc_key: recorded},
        immutable_counts_json={"document_versions": 1, "chunk_versions": 1},
    )
    repo = RagEvaluationRoundRepository(SimpleNamespace())  # type: ignore[arg-type]
    deletes: list[tuple[str, object]] = []

    async def lock_owned(*args: object, **kwargs: object) -> object:
        del args, kwargs
        return row

    async def lock_heads() -> list[SimpleNamespace]:
        return [head]

    async def head_projection(_head: object) -> dict[str, object]:
        return actual

    async def delete_block(*args: object, **kwargs: object) -> int:
        deletes.append(("block", (args, kwargs)))
        return 1

    async def delete_chunk(*args: object, **kwargs: object) -> int:
        deletes.append(("chunk", (args, kwargs)))
        return 1

    monkeypatch.setattr(repo, "lock_owned", lock_owned)
    monkeypatch.setattr(repo, "_lock_tenant_heads", lock_heads)
    monkeypatch.setattr(repo, "_head_projection", head_projection)
    monkeypatch.setattr(repo.block_repo, "delete_by_document_id", delete_block)
    monkeypatch.setattr(repo.chunk_repo, "delete_by_document_id", delete_chunk)

    with pytest.raises(EvaluationIsolationError) as caught:
        await repo.cleanup_current_projection(owner, terminal_state="abandoned")
    assert caught.value.reason_code == "projection_drift"
    assert deletes == []


@pytest.mark.asyncio
async def test_retrieval_ready_requires_all_three_recorded_projection_proofs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner = _identity(next_document_index=3)
    repo = RagEvaluationRoundRepository(SimpleNamespace())  # type: ignore[arg-type]
    events: list[object] = []

    async def lock_owned(*args: object, **kwargs: object) -> object:
        del args, kwargs
        return SimpleNamespace()

    async def lock_heads() -> list[SimpleNamespace]:
        return []

    async def prove(*args: object, **kwargs: object) -> list[object]:
        del args
        events.append(kwargs["require_all"])
        raise EvaluationIsolationError("projection_proof_incomplete")

    monkeypatch.setattr(repo, "lock_owned", lock_owned)
    monkeypatch.setattr(repo, "_lock_tenant_heads", lock_heads)
    monkeypatch.setattr(repo, "_prove_recorded_projection", prove)

    with pytest.raises(EvaluationIsolationError) as caught:
        await repo.prove_retrieval_ready(owner)
    assert caught.value.reason_code == "projection_proof_incomplete"
    assert events == [True]


@pytest.mark.asyncio
async def test_orphan_job_is_counted_when_evaluation_tenant_has_no_document_heads() -> None:
    session = _SequenceSession([_SequenceResult(scalar=1)])
    repo = RagEvaluationRoundRepository(session)  # type: ignore[arg-type]

    counts = await repo._current_counts([])  # noqa: SLF001 - exact no-head cleanup proof

    assert counts == {"documents": 0, "blocks": 0, "chunks": 0, "jobs": 1}
    sql = _sql(session.statements[0])
    assert "rag_ingestion_jobs.tenant_id =" in sql
    assert "rag_ingestion_jobs.doc_key IN" in sql
    params = session.statements[0].compile(dialect=postgresql.dialect()).params
    assert list(FORMAT_PARITY_DOC_KEYS) in params.values()


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


@pytest.mark.asyncio
async def test_retrieval_locator_coverage_requires_recorded_evidence_locator_proof() -> None:
    policy = _dataset().policies[0]
    case = next(item for item in policy.gold.cases if item.locator_constraints is not None)
    anchors = {anchor.anchor_id: anchor.text for anchor in policy.gold.anchors}
    hit_text = "\n".join(anchors[anchor_id] for anchor_id in case.evidence_anchor_ids)
    hit = PolicyRetrievalHit(
        doc_key=policy.doc_key,
        chunk_id="chunk-1",
        title=policy.title,
        section=str(case.expected_section),
        policy_version="v1",
        text=hit_text,
        score=0.99,
        rank=1,
    )
    service_result = SimpleNamespace(status="success", query_rewrite=None)
    without_evidence = PolicyRetrievalRun(
        status="success",
        hits=[hit],
        evidence_refs=[],
        best_score=0.99,
        original_query=case.question,
    )

    absent = retrieval_rounds_module._case_observation(
        policy_id=policy.doc_key,
        round_format="digital_pdf",
        case=case,
        anchors_by_id=anchors,
        service_result=service_result,
        recorded=without_evidence,
        locator_covered=False,
    )
    assert absent.hit_at_1 is True
    assert absent.semantic_anchor_hits == absent.semantic_anchor_total
    assert absent.locator_covered is False

    evidence_ref = EvidenceRefV1.build(
        tenant_id=str(FORMAT_PARITY_TENANT_ID),
        doc_key=policy.doc_key,
        chunk_id=hit.chunk_id,
        policy_version="v1",
        text=hit.text,
        retrieved_at="2026-08-10T00:00:00Z",
        retrieval_config_version="test",
        score=hit.score,
        rank=hit.rank,
    )
    recorded = PolicyRetrievalRun(
        status="success",
        hits=[hit],
        evidence_refs=[evidence_ref],
        best_score=0.99,
        original_query=case.question,
    )

    def provenance(page_number: int) -> dict[str, EvidenceProvenance]:
        return {
            evidence_ref.evidence_id: EvidenceProvenance(
                evidence_id=evidence_ref.evidence_id,
                doc_key=policy.doc_key,
                chunk_id=hit.chunk_id,
                source_locators=[
                    SourceLocator(
                        source_block_id="pdf:block:0001",
                        block_index=1,
                        block_type="paragraph",
                        page_number=page_number,
                    )
                ],
            )
        }

    document_id = uuid4()
    first_anchor = anchors[case.evidence_anchor_ids[0]]
    second_anchor = anchors[case.evidence_anchor_ids[1]]

    class _ExactProofRepository:
        def __init__(self, block_rows: list[SimpleNamespace]) -> None:
            self.block_rows = block_rows
            self.calls = 0

        async def prove_recorded_anchor_locators(self, **kwargs: object) -> bool:
            self.calls += 1
            return round_repo_module._source_blocks_prove_recorded_anchors(  # noqa: SLF001
                kwargs["candidates"],
                kwargs["requirements"],
                chunk_rows=[
                    SimpleNamespace(
                        doc_id=document_id,
                        chunk_id=hit.chunk_id,
                        content=hit.text,
                        source_block_refs_json=[
                            {
                                "source_block_id": block.source_block_id,
                                "page_number": block.page_number,
                                "text_hash": block.text_hash,
                            }
                            for block in self.block_rows
                        ],
                    )
                ],
                block_rows=self.block_rows,
                allowed_pdf_pages=kwargs["allowed_pdf_pages"],
            )

    page = case.locator_constraints.pdf_pages[0]
    single_block = SimpleNamespace(
        doc_id=document_id,
        source_block_id="pdf:block:0001",
        text=first_anchor,
        text_hash=evidence_text_hash(first_anchor),
        page_number=page,
    )
    requirements = [
        round_repo_module.AnchorLocatorRequirement(
            text=anchors[anchor_id],
            section=next(anchor.section for anchor in policy.gold.anchors if anchor.anchor_id == anchor_id),
        )
        for anchor_id in case.evidence_anchor_ids
    ]
    one_locator_repo = _ExactProofRepository([single_block])
    one_locator = await retrieval_rounds_module._recorded_locator_satisfies(  # noqa: SLF001
        one_locator_repo,  # type: ignore[arg-type]
        recorded,
        provenance_by_evidence_id=provenance(page),
        doc_key=policy.doc_key,
        expected_anchors=requirements,
        allowed_pdf_pages=case.locator_constraints.pdf_pages,
    )
    assert one_locator is False

    second_block = SimpleNamespace(
        doc_id=document_id,
        source_block_id="pdf:block:0002",
        text=second_anchor,
        text_hash=evidence_text_hash(second_anchor),
        page_number=page,
    )
    two_locator_provenance = provenance(page)
    two_locator_provenance[evidence_ref.evidence_id] = two_locator_provenance[
        evidence_ref.evidence_id
    ].model_copy(
        update={
            "source_locators": [
                *two_locator_provenance[evidence_ref.evidence_id].source_locators,
                SourceLocator(
                    source_block_id=second_block.source_block_id,
                    block_index=2,
                    block_type="paragraph",
                    page_number=page,
                ),
            ]
        }
    )
    two_locator = await retrieval_rounds_module._recorded_locator_satisfies(  # noqa: SLF001
        _ExactProofRepository([single_block, second_block]),  # type: ignore[arg-type]
        recorded,
        provenance_by_evidence_id=two_locator_provenance,
        doc_key=policy.doc_key,
        expected_anchors=requirements,
        allowed_pdf_pages=case.locator_constraints.pdf_pages,
    )
    assert two_locator is True

    hash_mismatch_ref = evidence_ref.model_copy(update={"text_hash": evidence_text_hash("tampered")})
    hash_mismatch_recorded = PolicyRetrievalRun(
        status=recorded.status,
        hits=recorded.hits,
        evidence_refs=[hash_mismatch_ref],
        best_score=recorded.best_score,
        original_query=recorded.original_query,
    )
    mismatch_repo = _ExactProofRepository([single_block, second_block])
    hash_mismatch = await retrieval_rounds_module._recorded_locator_satisfies(  # noqa: SLF001
        mismatch_repo,  # type: ignore[arg-type]
        hash_mismatch_recorded,
        provenance_by_evidence_id=two_locator_provenance,
        doc_key=policy.doc_key,
        expected_anchors=requirements,
        allowed_pdf_pages=case.locator_constraints.pdf_pages,
    )
    assert hash_mismatch is False
    assert mismatch_repo.calls == 0


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
        round_result: dict[str, object] | None = None,
    ) -> EvaluationRoundIdentity:
        del terminal_state, failure_code, round_result
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


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["provider", "full-provider"])
@pytest.mark.parametrize(
    "reason_code",
    [
        "manifest_file_invalid",
        "gold_file_invalid",
        "fixture_file_invalid",
        "fixture_checksum_mismatch",
    ],
)
async def test_contract_load_read_and_hash_failures_are_execution_errors_for_both_provider_modes(
    monkeypatch: pytest.MonkeyPatch,
    mode: str,
    reason_code: str,
) -> None:
    def fail_contract(*args: object, **kwargs: object) -> object:
        del args, kwargs
        raise FormatParityContractError(reason_code)

    monkeypatch.setattr(format_parity_cli, "load_format_parity_contract", fail_contract)
    args = SimpleNamespace(
        mode=mode,
        manifest="missing-manifest.jsonl",
        gold="missing-gold.json",
        tenant_id=str(FORMAT_PARITY_TENANT_ID),
        owner_marker=FORMAT_PARITY_OWNER_MARKER,
        run_token=str(uuid4()),
        expected_rollout_version=2,
        generated_at="2026-08-10T00:00:00Z",
    )

    result = (
        await format_parity_cli.run_provider(args)
        if mode == "provider"
        else await format_parity_cli.run_full_provider(args)
    )
    payload = result.model_dump(mode="json")

    assert payload["outcome"] == "execution_error"
    assert payload["baseline_eligible"] is False
    if mode == "provider":
        assert payload["rounds"] == []
        assert payload["prerequisites"][0] == {
            "name": "evaluation_contract",
            "available": False,
            "reason_code": "evaluation_contract_invalid",
        }
    else:
        assert payload["prerequisites"] == ["evaluation_contract"]
        assert payload["reason_codes"] == ["evaluation_contract_invalid"]
