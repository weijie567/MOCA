from __future__ import annotations

import inspect
from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.agent.nodes.investigate import investigate
from src.db.models import (
    AgentRun,
    AgentTraceEvent,
    EvidenceSnapshotDependency,
    PolicyChunk,
    PolicyChunkVersion,
    PolicyDocument,
    PolicyDocumentVersion,
)
from src.knowledge.schemas import EvidenceRefV1
from src.knowledge.text_hash import evidence_text_hash
from src.platform.trusted_context import MerchantScopeV1, TrustedContext
from src.repositories.evidence_version_repo import EvidenceVersionRepository
from src.replay.service import ReplayService
from src.replay.schemas import ReplayEvidenceSnapshotV1
from src.tools.catalog import ToolCatalog
from src.tools.contracts import (
    ToolCallContext,
    ToolInvocationOutcome,
    ToolPolicyDecision,
    ToolResultV2,
    ToolViewV1,
)
from src.tools.policy import project_prompt_safe_input_schema
from src.tools.projection import ToolResultProjector


class _CanonicalPolicyPlatform:
    def __init__(self, result: ToolResultV2) -> None:
        descriptor = ToolCatalog().descriptor("search_policy")
        assert descriptor is not None
        self._descriptor = descriptor
        self._result = result

    def descriptor(self, name: str):
        return self._descriptor if name == self._descriptor.name else None

    def event_family(self, name: str) -> str | None:
        return "rag_retrieval" if name == self._descriptor.name else None

    async def visible_tools(
        self,
        *,
        caller: str,
        ctx: ToolCallContext,
        session: Any = None,
    ) -> list[ToolViewV1]:
        assert caller == "investigate"
        return [
            ToolViewV1(
                name=self._descriptor.name,
                description=self._descriptor.description,
                input_schema=project_prompt_safe_input_schema(self._descriptor.input_schema),
                safe_usage_notes=[],
                result_contract_version="tool_result.v2",
            )
        ]

    async def invoke(
        self,
        tool_name: str,
        args: dict[str, Any],
        ctx: ToolCallContext,
        *,
        session: Any = None,
    ) -> ToolInvocationOutcome:
        assert tool_name == "search_policy"
        projection = ToolResultProjector().project(
            tool_name=tool_name,
            result=self._result,
            tool_call_id=ctx.tool_call_id,
        )
        return ToolInvocationOutcome(
            tool_result=self._result,
            projection=projection,
            policy_decision=ToolPolicyDecision(
                tool_name=tool_name,
                caller="investigate",
                decision_stage="runtime_auth",
                decision="allowed",
                reason_codes=["visible"],
                required_scopes=[],
                matched_scope=None,
                policy_version="tool_policy.v1",
                data_classification="internal",
                runtime_available=True,
            ),
            policy_event_id=None,
        )


async def _canonical_fixture(
    session: AsyncSession,
    seeded_session: dict[str, Any],
) -> tuple[AgentRun, EvidenceRefV1, PolicyDocumentVersion, PolicyChunkVersion]:
    tenant = seeded_session["tenant"]
    user = seeded_session["users"]["cs_zhang"]
    run = AgentRun(
        id=uuid4(),
        tenant_id=tenant.id,
        user_id=user.id,
        thread_id=f"production-evidence-{uuid4()}",
        input_query="退款政策是什么？",
        final_status="running",
        started_at=datetime.now(UTC),
    )
    document = PolicyDocument(
        id=uuid4(),
        tenant_id=tenant.id,
        doc_key="refund_policy",
        doc_type="refund",
        title="Refund Policy",
        effective_date=date(2026, 1, 1),
        risk_level="medium",
        version=3,
        content="退款政策原始文档",
        source_type="policy_markdown",
        source_checksum="sha256:source",
    )
    retention_until = datetime.now(UTC) + timedelta(days=30)
    document_version = PolicyDocumentVersion(
        id=uuid4(),
        tenant_id=tenant.id,
        policy_document_id=document.id,
        scope_type="tenant_policy",
        scope_id=str(tenant.id),
        doc_key=document.doc_key,
        document_version=3,
        content=document.content,
        content_hash=evidence_text_hash(document.content),
        source_locator_json={
            "source_type": "policy_markdown",
            "source_uri": "policies/refund.md",
        },
        lifecycle_status="active",
        retention_until=retention_until,
    )
    chunk_content = "退款必须在原支付渠道处理。"
    chunk_version = PolicyChunkVersion(
        id=uuid4(),
        tenant_id=tenant.id,
        policy_document_version_id=document_version.id,
        scope_type="tenant_policy",
        scope_id=str(tenant.id),
        doc_key=document.doc_key,
        document_version=3,
        chunk_id="refund_001",
        chunk_version=2,
        content=chunk_content,
        text_hash=evidence_text_hash(chunk_content),
        source_locator_json={
            "source_type": "policy_markdown",
            "source_uri": "policies/refund.md",
            "source_block_refs": ["block-1"],
        },
        lifecycle_status="active",
        retention_until=retention_until,
    )
    session.add_all([run, document, document_version])
    await session.flush()
    current_chunk = PolicyChunk(
        id=uuid4(),
        tenant_id=tenant.id,
        doc_id=document.id,
        chunk_id="refund_001",
        section="Refund",
        content=chunk_content,
        search_text=chunk_content,
        source_block_refs_json=[{"source_block_id": "block-1"}],
        ocr_metadata_json={},
        risk_level="medium",
        effective_date=date(2026, 1, 1),
    )
    session.add_all([current_chunk, chunk_version])
    await session.flush()

    resolution = await EvidenceVersionRepository(session).mint_for_chunk_version(
        chunk_version,
        expected_tenant_id=tenant.id,
        expected_scope_type="tenant_policy",
        expected_scope_id=str(tenant.id),
    )
    assert resolution.identity is not None
    ref = EvidenceVersionRepository.evidence_ref_from_identity(
        resolution.identity,
        retrieved_at="2026-08-05T00:00:00+00:00",
        retrieval_config_version="retrieval.v3",
        score=0.91,
        rank=1,
    )
    return run, ref, document_version, chunk_version


def _tool_result(ref: EvidenceRefV1) -> ToolResultV2:
    return ToolResultV2(
        status="success",
        data={"retrieval_status": "strong_evidence", "best_score": 0.91},
        summary="policy found",
        source_system="policy_knowledge_service",
        data_freshness_at=None,
        policy_evidence_refs=[ref],
        business_fact_refs=[],
        error=None,
        retryable=False,
        retry_after_ms=None,
        latency_ms=3,
        audit_ref="audit/policy/refund_001",
    )


def _state(run: AgentRun) -> dict[str, Any]:
    return {
        "thread_id": run.thread_id,
        "tenant_id": str(run.tenant_id),
        "user_id": str(run.user_id),
        "role": "support",
        "current_run_id": str(run.id),
        "user_query": "退款政策是什么？",
        "_investigate_plan": [
            {
                "next_tool": "search_policy",
                "args": {"query": "退款政策"},
                "reason": "load policy evidence",
            }
        ],
    }


def _trusted_context(run: AgentRun) -> TrustedContext:
    return TrustedContext(
        tenant_id=str(run.tenant_id),
        user_id=str(run.user_id),
        role="support",
        permissions=["tool:search_policy"],
        merchant_scope=MerchantScopeV1(merchant_ids=["*"]),
        session_id=None,
        thread_id=run.thread_id,
        run_id=str(run.id),
        trace_id=f"trace-{run.id}",
        locale=None,
    )


def _config(
    run: AgentRun,
    platform: _CanonicalPolicyPlatform,
    *,
    session: AsyncSession | None = None,
    event_emitter: Any = None,
) -> dict[str, Any]:
    return {
        "configurable": {
            "tool_platform": platform,
            "session": session,
            "event_emitter": event_emitter,
            "trusted_context": _trusted_context(run).model_dump(mode="json"),
            "node_operation_id": uuid4(),
            "max_iterations": 1,
            "max_attempts": 1,
        }
    }


@pytest.mark.asyncio
async def test_configurable_emitter_receives_identical_typed_canonical_refs(
    session: AsyncSession,
    seeded_session: dict[str, Any],
) -> None:
    run, ref, _, _ = await _canonical_fixture(session, seeded_session)
    captured: list[dict[str, Any]] = []

    async def event_emitter(**payload: Any) -> None:
        captured.append(payload)

    await investigate(
        _state(run),
        _config(run, _CanonicalPolicyPlatform(_tool_result(ref)), event_emitter=event_emitter),
    )

    assert [event["event_type"] for event in captured] == [
        "rag_retrieval_started",
        "rag_retrieval_completed",
    ]
    assert captured[0]["canonical_evidence_refs"] == []
    assert captured[1]["canonical_evidence_refs"] == [ref]
    assert captured[1]["canonical_evidence_refs"][0] is ref
    assert all(isinstance(item, EvidenceRefV1) for item in captured[1]["canonical_evidence_refs"])
    assert "evidence_snapshot_refs" not in captured[1]


@pytest.mark.asyncio
async def test_investigate_event_replays_exact_original_evidence(
    session: AsyncSession,
    seeded_session: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run, ref, document_version, chunk_version = await _canonical_fixture(session, seeded_session)
    captured_builder_output: list[dict[str, Any]] = []
    builder = ReplayService._build_replay_evidence_snapshots

    async def capture_builder(self: ReplayService, **kwargs: Any):
        snapshots = await builder(self, **kwargs)
        captured_builder_output.extend(snapshot.model_dump(mode="json") for snapshot in snapshots)
        return snapshots

    monkeypatch.setattr(ReplayService, "_build_replay_evidence_snapshots", capture_builder)

    await investigate(
        _state(run),
        _config(run, _CanonicalPolicyPlatform(_tool_result(ref)), session=session, event_emitter=None),
    )

    events = list(
        (
            await session.execute(
                select(AgentTraceEvent)
                .where(AgentTraceEvent.run_id == run.id)
                .order_by(AgentTraceEvent.sequence)
            )
        ).scalars()
    )
    terminal = events[-1]
    dependencies = list(
        (
            await session.execute(
                select(EvidenceSnapshotDependency).where(EvidenceSnapshotDependency.event_id == terminal.event_id)
            )
        ).scalars()
    )

    assert [event.event_type for event in events] == ["rag_retrieval_started", "rag_retrieval_completed"]
    assert events[0].evidence_snapshot_refs_json == []
    assert terminal.evidence_snapshot_refs_json == captured_builder_output
    assert terminal.evidence_snapshot_refs_json == [
        {
            "schema_version": "replay_evidence_snapshot.v1",
            "canonical_evidence_ref": ref.model_dump(mode="json"),
            "scope_type": "tenant_policy",
            "scope_id": str(run.tenant_id),
            "document_version_id": str(document_version.id),
            "chunk_version_id": str(chunk_version.id),
            "document_version": 3,
            "chunk_version": 2,
            "canonical_identity_hash": ref.evidence_id,
            "captured_lifecycle_status": "current",
            "retained_content_hash": chunk_version.text_hash,
            "retained_content_locator": chunk_version.source_locator_json,
            "compatibility_provenance": {
                "resolution_status": "canonical",
                "source": "canonical_ref_append",
            },
            "retention_until": chunk_version.retention_until.isoformat().replace("+00:00", "Z"),
        }
    ]
    assert len(dependencies) == 1
    dependency = dependencies[0]
    assert dependency.tenant_id == run.tenant_id
    assert dependency.event_id == terminal.event_id
    assert dependency.document_version_id == document_version.id
    assert dependency.chunk_version_id == chunk_version.id
    assert dependency.retention_until == chunk_version.retention_until


@pytest.mark.asyncio
async def test_new_append_rejects_legacy_raw_input_and_mixed_forged_refs_atomically(
    session: AsyncSession,
    seeded_session: dict[str, Any],
) -> None:
    run, ref, _, _ = await _canonical_fixture(session, seeded_session)
    service = ReplayService(session)
    baseline = await _row_counts(session, run.id)
    append_kwargs = {
        "run_id": run.id,
        "tenant_id": run.tenant_id,
        "thread_id": run.thread_id,
        "event_type": "rag_retrieval_completed",
        "actor": {"type": "agent", "id": "moca"},
        "resource_refs": {"tool": "search_policy"},
        "redacted_payload": {"status": "completed"},
        "operation_id": uuid4(),
        "attempt": 1,
    }

    assert "evidence_refs_json" not in inspect.signature(service.append_event).parameters
    with pytest.raises(TypeError, match="evidence_refs_json"):
        await service.append_event(  # type: ignore[call-arg]
            **append_kwargs,
            evidence_refs_json=[{"evidence_id": ref.evidence_id}],
        )
    assert await _row_counts(session, run.id) == baseline

    forged = ref.model_copy(update={"text_hash": "sha256:" + "f" * 64})
    with pytest.raises(ValueError, match="evidence unavailable"):
        await service.append_event(
            **append_kwargs,
            canonical_evidence_refs=[ref, forged],
        )
    assert await _row_counts(session, run.id) == baseline

    cross_scope = ref.model_copy(update={"scope_id": str(uuid4())})
    with pytest.raises(ValueError, match="evidence unavailable"):
        await service.append_event(
            **append_kwargs,
            canonical_evidence_refs=[cross_scope],
        )
    assert await _row_counts(session, run.id) == baseline


async def _row_counts(session: AsyncSession, run_id: UUID) -> tuple[int, int, int]:
    event_count = await session.scalar(
        select(func.count()).select_from(AgentTraceEvent).where(AgentTraceEvent.run_id == run_id)
    )
    snapshot_count = await session.scalar(
        select(func.count())
        .select_from(AgentTraceEvent)
        .where(
            AgentTraceEvent.run_id == run_id,
            AgentTraceEvent.evidence_snapshot_refs_json.is_not(None),
            AgentTraceEvent.evidence_snapshot_refs_json != [],
        )
    )
    dependency_count = await session.scalar(
        select(func.count())
        .select_from(EvidenceSnapshotDependency)
        .join(AgentTraceEvent, AgentTraceEvent.event_id == EvidenceSnapshotDependency.event_id)
        .where(AgentTraceEvent.run_id == run_id)
    )
    return int(event_count or 0), int(snapshot_count or 0), int(dependency_count or 0)


@pytest.mark.asyncio
async def test_minimal_decision_projection_exposes_optional_typed_snapshot(
    session: AsyncSession,
    seeded_session: dict[str, Any],
) -> None:
    run, ref, _, _ = await _canonical_fixture(session, seeded_session)

    event = await ReplayService(session).append_event(
        run_id=run.id,
        tenant_id=run.tenant_id,
        thread_id=run.thread_id,
        event_type="rag_retrieval_completed",
        actor={"type": "agent", "id": "moca"},
        resource_refs={"tool": "search_policy"},
        redacted_payload={"status": "completed"},
        operation_id=uuid4(),
        attempt=1,
        schema_version="minimal_event_envelope.v1",
        canonical_evidence_refs=[ref],
    )

    assert ReplayEvidenceSnapshotV1.model_validate(event["evidence_snapshot_refs"][0])


@pytest.mark.asyncio
async def test_replay_resolves_retained_original_through_lifecycle_changes_and_blocks_purge(
    session: AsyncSession,
    seeded_session: dict[str, Any],
) -> None:
    run, ref, original_document, original_chunk = await _canonical_fixture(session, seeded_session)
    original_content = original_chunk.content
    original_hash = original_chunk.text_hash
    original_locator = dict(original_chunk.source_locator_json)
    await investigate(
        _state(run),
        _config(run, _CanonicalPolicyPlatform(_tool_result(ref)), session=session, event_emitter=None),
    )

    current_document = await session.get(PolicyDocument, original_document.policy_document_id)
    assert current_document is not None
    current_chunk = (
        await session.execute(
            select(PolicyChunk).where(
                PolicyChunk.tenant_id == run.tenant_id,
                PolicyChunk.doc_id == current_document.id,
                PolicyChunk.chunk_id == original_chunk.chunk_id,
            )
        )
    ).scalar_one()
    current_document.version = 4
    current_document.content = "退款政策重新摄取后的文档"
    current_chunk.content = "新版本允许不同的退款渠道。"
    current_chunk.search_text = current_chunk.content
    await EvidenceVersionRepository(session).append_immutable_version(
        tenant_id=run.tenant_id,
        document=current_document,
        chunks=[current_chunk],
        write_sequence=2,
    )

    for stored_status, expected_status in (
        ("superseded", "superseded"),
        ("corrected", "corrected"),
        ("expired", "expired"),
        ("tombstoned", "tombstoned"),
    ):
        original_document.lifecycle_status = stored_status
        original_chunk.lifecycle_status = stored_status
        if stored_status == "expired":
            original_document.expired_at = original_chunk.expired_at = datetime.now(UTC)
        if stored_status == "tombstoned":
            original_document.tombstoned_at = original_chunk.tombstoned_at = datetime.now(UTC)
        await session.flush()

        replay = await ReplayService(session).get_replay(run.id)
        terminal = replay["timeline"][-1]
        resolved = terminal["evidence_snapshot_refs"][0]
        assert resolved["canonical_evidence_ref"] == ref.model_dump(mode="python")
        assert resolved["scope_type"] == "tenant_policy"
        assert resolved["scope_id"] == str(run.tenant_id)
        assert resolved["document_version_id"] == str(original_document.id)
        assert resolved["chunk_version_id"] == str(original_chunk.id)
        assert resolved["retained_content"] == original_content
        assert resolved["retained_content_hash"] == original_hash
        assert resolved["retained_content_locator"] == original_locator
        assert resolved["current_lifecycle_status"] == expected_status
        assert "新版本允许不同的退款渠道" not in str(resolved)

    await session.commit()
    retained_chunk = await session.get(PolicyChunkVersion, original_chunk.id)
    assert retained_chunk is not None
    await session.delete(retained_chunk)
    with pytest.raises(IntegrityError):
        await session.flush()
    await session.rollback()


@pytest.mark.asyncio
async def test_persisted_legacy_json_resolves_only_from_existing_event_and_marks_unresolved(
    session: AsyncSession,
    seeded_session: dict[str, Any],
) -> None:
    run, ref, _, original_chunk = await _canonical_fixture(session, seeded_session)
    legacy_ref = EvidenceRefV1.build(
        tenant_id=str(run.tenant_id),
        doc_key=ref.doc_key,
        chunk_id=ref.chunk_id,
        policy_version=ref.policy_version,
        text=original_chunk.content,
        retrieved_at=ref.retrieved_at,
        retrieval_config_version=ref.retrieval_config_version,
        rank=ref.rank,
    ).model_dump(mode="json")
    missing_ref = dict(legacy_ref)
    missing_ref["evidence_id"] = "missing/chunk@v1"
    missing_ref["doc_key"] = "missing"
    missing_ref["chunk_id"] = "chunk"
    missing_ref["policy_version"] = "v1"
    session.add_all(
        [
            AgentTraceEvent(
                event_id=uuid4(),
                run_id=run.id,
                sequence=1,
                tenant_id=run.tenant_id,
                thread_id=run.thread_id,
                event_type="approval_requested",
                schema_version="minimal_event_envelope.v1",
                occurred_at=datetime.now(UTC),
                actor={"type": "system", "id": "legacy-import"},
                resource_refs={},
                redaction_policy_version="redaction.v1",
                redacted_payload={"status": "pending"},
                evidence_refs_json=[legacy_ref],
            ),
            AgentTraceEvent(
                event_id=uuid4(),
                run_id=run.id,
                sequence=2,
                tenant_id=run.tenant_id,
                thread_id=run.thread_id,
                event_type="approval_requested",
                schema_version="minimal_event_envelope.v1",
                occurred_at=datetime.now(UTC),
                actor={"type": "system", "id": "legacy-import"},
                resource_refs={},
                redaction_policy_version="redaction.v1",
                redacted_payload={"status": "pending"},
                evidence_refs_json=[missing_ref],
            ),
        ]
    )
    await session.flush()

    replay = await ReplayService(session).get_replay(run.id)

    resolved = replay["timeline"][0]["evidence_snapshot_refs"][0]
    assert resolved["compatibility_provenance"] == {
        "resolution_status": "legacy_resolved",
        "source": "persisted_legacy_event",
    }
    assert resolved["retained_content"] == original_chunk.content
    assert replay["timeline"][1]["evidence_snapshot_refs"] == []
    assert replay["timeline"][1]["provenance"]["evidence_resolution_status"] == "legacy_unresolved"


@pytest.mark.asyncio
async def test_replay_api_returns_generic_404_for_forged_snapshot_binding(
    client: AsyncClient,
    session: AsyncSession,
    seeded_session: dict[str, Any],
) -> None:
    run, ref, _, _ = await _canonical_fixture(session, seeded_session)
    await investigate(
        _state(run),
        _config(run, _CanonicalPolicyPlatform(_tool_result(ref)), session=session, event_emitter=None),
    )
    terminal = (
        await session.execute(
            select(AgentTraceEvent)
            .where(AgentTraceEvent.run_id == run.id)
            .order_by(AgentTraceEvent.sequence.desc())
            .limit(1)
        )
    ).scalar_one()
    forged = [dict(item) for item in terminal.evidence_snapshot_refs_json or []]
    forged[0] = {**forged[0], "scope_id": str(uuid4())}
    terminal.evidence_snapshot_refs_json = forged
    await session.commit()

    login = await client.post("/api/v1/auth/login", json={"username": "cs_zhang", "password": "moca2024"})
    response = await client.get(
        f"/api/v1/agent-runs/{run.id}/replay",
        headers={"Authorization": f"Bearer {login.json()['data']['access_token']}"},
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"
    assert ref.evidence_id not in response.text
