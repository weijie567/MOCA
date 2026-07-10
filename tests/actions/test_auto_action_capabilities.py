from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.actions.service import ActionService
from src.agent.trace import write_agent_run
from src.approvals.snapshot_service import compute_action_payload_hash, persist_action_safety_snapshot
from src.db.models import ActionDraft, AgentRun, AgentTraceEvent


HANDLER = "create_coupon_grant_draft"


def _fixed_millisecond_now() -> datetime:
    now = datetime.now(UTC)
    return now.replace(microsecond=(now.microsecond // 1000) * 1000)


def _capability_api():
    from src.actions.capabilities import (
        AUTO_ACTION_CAPABILITY_KEY_VERSION,
        AUTO_ACTION_CAPABILITY_SCHEMA_VERSION,
        AutoActionCapabilityService,
        CapabilityMintError,
        CapabilityVerificationError,
        capability_ref_digest,
        compute_risk_decision_hash,
    )
    from src.db.models import AutoActionCapability

    return {
        "key_version": AUTO_ACTION_CAPABILITY_KEY_VERSION,
        "schema_version": AUTO_ACTION_CAPABILITY_SCHEMA_VERSION,
        "service": AutoActionCapabilityService,
        "mint_error": CapabilityMintError,
        "verification_error": CapabilityVerificationError,
        "ref_digest": capability_ref_digest,
        "risk_hash": compute_risk_decision_hash,
        "model": AutoActionCapability,
    }


async def _create_run(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    actor_id: UUID,
    target_merchant_id: str,
) -> UUID:
    run_id = uuid4()
    now = datetime.now(UTC)
    await write_agent_run(
        session,
        run_id=str(run_id),
        thread_id=f"auto-capability-{run_id}",
        tenant_id=str(tenant_id),
        user_id=str(actor_id),
        input_query="create a bounded demo draft",
        final_status="pending",
        final_response=None,
        started_at=now,
        completed_at=None,
        total_latency_ms=None,
    )
    run = await session.get(AgentRun, run_id)
    assert run is not None
    run.scope_classification = "business_merchant"
    run.target_merchant_id = target_merchant_id
    run.target_merchant_ref = {
        "schema_version": "target_merchant_binding.v1",
        "target_merchant_id": target_merchant_id,
        "source": "business_fact_ref",
        "business_fact_ref": {
            "schema_version": "business_fact_ref.v1",
            "tenant_id": str(tenant_id),
            "source_system": "moca_demo",
            "resource_type": "refund_case",
            "resource_id": "RF-1001",
            "resource_version": "v1",
            "data_freshness_at": "2026-07-10T00:00:00Z",
            "retrieved_at": "2026-07-10T00:01:00Z",
        },
    }
    run.scope_source = "target_merchant_binding_v1"
    run.scope_reason_codes = []
    await session.flush()
    return run_id


def _business_fact_ref(*, tenant_id: UUID) -> dict[str, Any]:
    return {
        "schema_version": "business_fact_ref.v1",
        "tenant_id": str(tenant_id),
        "source_system": "moca_demo",
        "resource_type": "refund_case",
        "resource_id": "RF-1001",
        "resource_version": "v1",
        "data_freshness_at": "2026-07-10T00:00:00Z",
        "retrieved_at": "2026-07-10T00:01:00Z",
    }


def _evidence_ref(*, tenant_id: UUID) -> dict[str, Any]:
    return {
        "schema_version": "evidence_ref.v1",
        "tenant_id": str(tenant_id),
        "evidence_id": "refund-policy/chunk-001@v3",
        "doc_key": "refund-policy",
        "chunk_id": "chunk-001",
        "policy_version": "v3",
        "text_hash": "sha256:" + "e" * 64,
        "retrieved_at": "2026-07-10T00:00:00.000Z",
        "retrieval_config_version": "retrieval.v1",
        "rank": 1,
    }


async def _capability_context(
    session: AsyncSession,
    seeded_session,
    *,
    commit: bool = False,
) -> dict[str, Any]:
    api = _capability_api()
    tenant_id = seeded_session["tenant"].id
    actor_id = seeded_session["users"]["cs_zhang"].id
    target_merchant_id = str(seeded_session["merchant"].id)
    run_id = await _create_run(
        session,
        tenant_id=tenant_id,
        actor_id=actor_id,
        target_merchant_id=target_merchant_id,
    )
    business_fact_ref = _business_fact_ref(tenant_id=tenant_id)
    target_merchant_ref = {
        "schema_version": "target_merchant_binding.v1",
        "target_merchant_id": target_merchant_id,
        "source": "business_fact_ref",
        "business_fact_ref": business_fact_ref,
    }
    proposed_action = {
        "schema_version": "proposed_action.v1",
        "tenant_id": str(tenant_id),
        "run_id": str(run_id),
        "action_id": "act-auto-capability",
        "action_type": "issue_coupon",
        "target_type": "refund_case",
        "target_id": "RF-1001",
        "amount": "25.00",
        "currency": "CNY",
        "args": {"amount": "25.00", "currency": "CNY"},
        "reason": "Low-risk policy compensation.",
        "evidence_refs": [],
    }
    action_payload_hash = compute_action_payload_hash(proposed_action)
    snapshot = await persist_action_safety_snapshot(
        session,
        tenant_id=tenant_id,
        run_id=run_id,
        proposed_action=proposed_action,
        action_payload_hash=action_payload_hash,
        policy_config_version="approval-policy.v1",
        risk_config_version="risk-rules.v1",
        retrieval_config_version="retrieval.v1",
        evidence_refs=[_evidence_ref(tenant_id=tenant_id)],
        target_merchant_id=target_merchant_id,
        target_merchant_ref=target_merchant_ref,
        business_fact_refs=[business_fact_ref],
        created_at=_fixed_millisecond_now(),
        created_by=actor_id,
    )
    risk_decision_ref = f"risk_decision:{run_id}:{action_payload_hash}"
    risk_decision = {
        "schema_version": "risk_decision.v1",
        "tenant_id": str(tenant_id),
        "run_id": str(run_id),
        "action_id": "act-auto-capability",
        "action_payload_hash": action_payload_hash,
        "risk_level": "low",
        "reason_codes": ["auto_allowed_candidate", "risk_disposition:allow"],
        "policy_config_version": "approval-policy.v1",
        "risk_config_version": "risk-rules.v1",
        "approval_required": False,
        "evaluated_at": "2026-07-10T00:02:00.000Z",
        "risk_rule_ref": "risk:low:coupon_under_50",
        "risk_reason": "Deterministic low-risk allow.",
    }
    mint_kwargs = {
        "tenant_id": tenant_id,
        "actor_id": actor_id,
        "run_id": run_id,
        "target_merchant_id": target_merchant_id,
        "canonical_action": "issue_coupon",
        "action_payload_hash": action_payload_hash,
        "safety_snapshot_ref": snapshot.safety_snapshot_ref,
        "safety_snapshot_hash": snapshot.safety_snapshot_hash,
        "risk_decision_ref": risk_decision_ref,
        "risk_decision": risk_decision,
        "risk_disposition": "allow",
        "handler": HANDLER,
    }
    grant = await api["service"](session).mint(**mint_kwargs)
    if commit:
        await session.commit()
    return {
        "api": api,
        "tenant_id": tenant_id,
        "actor_id": actor_id,
        "run_id": run_id,
        "target_merchant_id": target_merchant_id,
        "target_merchant_ref": target_merchant_ref,
        "business_fact_refs": [business_fact_ref],
        "verified_evidence_refs": [_evidence_ref(tenant_id=tenant_id)],
        "proposed_action": proposed_action,
        "action_payload_hash": action_payload_hash,
        "snapshot_ref": snapshot.safety_snapshot_ref,
        "snapshot_hash": snapshot.safety_snapshot_hash,
        "risk_decision_ref": risk_decision_ref,
        "risk_decision": risk_decision,
        "grant": grant,
        "mint_kwargs": mint_kwargs,
    }


def _draft_kwargs(context: dict[str, Any], **overrides: Any) -> dict[str, Any]:
    kwargs = {
        "tenant_id": str(context["tenant_id"]),
        "user_id": str(context["actor_id"]),
        "run_id": str(context["run_id"]),
        "approval_request_id": None,
        "idempotency_key": "caller-value-is-not-authority",
        "action_type": "issue_coupon",
        "payload": dict(context["proposed_action"]),
        "action_payload_hash": context["action_payload_hash"],
        "safety_snapshot_ref": context["snapshot_ref"],
        "safety_snapshot_hash": context["snapshot_hash"],
        "target_merchant_id": context["target_merchant_id"],
        "target_merchant_ref": context["target_merchant_ref"],
        "business_fact_refs": context["business_fact_refs"],
        "verified_evidence_refs": context["verified_evidence_refs"],
        "claim_verification_ref": None,
        "claim_verification_summary": {"overall_status": "verified"},
        "risk_decision_ref": context["risk_decision_ref"],
        "risk_decision": context["risk_decision"],
        "auto_action_capability_ref": context["grant"].capability_ref,
        "thread_id": f"auto-capability-{context['run_id']}",
        "trace_id": "trace-auto-capability",
    }
    kwargs.update(overrides)
    return kwargs


@pytest.mark.asyncio
async def test_mint_persists_hashed_opaque_short_lived_capability_and_exact_bindings(
    session: AsyncSession,
    seeded_session,
):
    context = await _capability_context(session, seeded_session)
    api = context["api"]
    grant = context["grant"]
    row = (
        await session.execute(
            select(api["model"]).where(api["model"].opaque_ref == api["ref_digest"](grant.capability_ref))
        )
    ).scalar_one()

    assert grant.capability_ref.startswith("aac_")
    assert grant.capability_ref != row.opaque_ref
    assert row.schema_version == api["schema_version"]
    assert row.key_version == api["key_version"]
    assert row.status == "issued"
    assert row.nonce
    assert row.tenant_id == context["tenant_id"]
    assert row.actor_id == context["actor_id"]
    assert row.run_id == context["run_id"]
    assert row.target_merchant_id == context["target_merchant_id"]
    assert row.canonical_action == "issue_coupon"
    assert row.action_payload_hash == context["action_payload_hash"]
    assert row.safety_snapshot_ref == context["snapshot_ref"]
    assert row.safety_snapshot_hash == context["snapshot_hash"]
    assert row.risk_decision_ref == context["risk_decision_ref"]
    assert row.risk_decision_hash == api["risk_hash"](context["risk_decision"])
    assert row.risk_disposition == "allow"
    assert row.handler == HANDLER
    assert timedelta(0) < grant.expires_at - row.issued_at <= timedelta(minutes=5)
    assert row.consumed_at is None
    assert row.resulting_draft_id is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("override", "value"),
    [
        ("actor_id", uuid4()),
        ("canonical_action", "approve_refund"),
        ("risk_disposition", "manual_review"),
        ("handler", "execute_coupon_grant"),
        ("safety_snapshot_hash", "sha256:" + "0" * 64),
        ("ttl", timedelta(minutes=6)),
    ],
)
async def test_mint_rejects_untrusted_or_non_allow_prerequisites_without_row(
    session: AsyncSession,
    seeded_session,
    override: str,
    value: Any,
):
    context = await _capability_context(session, seeded_session)
    api = context["api"]
    await session.delete(
        (
            await session.execute(select(api["model"]).where(api["model"].run_id == context["run_id"]))
        ).scalar_one()
    )
    await session.flush()
    kwargs = {**context["mint_kwargs"], override: value}

    with pytest.raises(api["mint_error"]):
        await api["service"](session).mint(**kwargs)

    assert (
        await session.scalar(select(func.count()).select_from(api["model"]).where(api["model"].run_id == context["run_id"]))
    ) == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "risk_patch",
    [
        {"risk_level": "medium"},
        {"approval_required": True},
        {"risk_rule_ref": None},
    ],
)
async def test_mint_rejects_non_deterministic_allow_risk_decisions(
    session: AsyncSession,
    seeded_session,
    risk_patch: dict[str, Any],
):
    context = await _capability_context(session, seeded_session)
    api = context["api"]
    row = await session.scalar(select(api["model"]).where(api["model"].run_id == context["run_id"]))
    assert row is not None
    await session.delete(row)
    await session.flush()
    risk_decision = {**context["risk_decision"], **risk_patch}

    with pytest.raises(api["mint_error"]):
        await api["service"](session).mint(**{**context["mint_kwargs"], "risk_decision": risk_decision})

    assert await session.scalar(select(func.count()).select_from(api["model"])) == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("override", "value_factory"),
    [
        ("tenant_id", lambda _ctx: str(uuid4())),
        ("user_id", lambda _ctx: str(uuid4())),
        ("run_id", lambda _ctx: str(uuid4())),
        ("target_merchant_id", lambda _ctx: "merchant-other"),
        ("action_type", lambda _ctx: "approve_refund"),
        ("action_payload_hash", lambda _ctx: "sha256:" + "0" * 64),
        ("safety_snapshot_ref", lambda _ctx: "snapshot:other"),
        ("safety_snapshot_hash", lambda _ctx: "sha256:" + "0" * 64),
        ("risk_decision_ref", lambda _ctx: "risk_decision:other"),
        (
            "risk_decision",
            lambda ctx: {**ctx["risk_decision"], "risk_reason": "tampered before consume"},
        ),
        ("auto_action_capability_ref", lambda _ctx: "aac_unknown"),
    ],
)
async def test_capability_confused_deputy_matrix_creates_zero_drafts(
    session: AsyncSession,
    seeded_session,
    override: str,
    value_factory,
):
    context = await _capability_context(session, seeded_session)
    result = await ActionService(session).create_coupon_grant_draft(
        **_draft_kwargs(context, **{override: value_factory(context)})
    )

    assert result["status"] == "error"
    assert await session.scalar(select(func.count()).select_from(ActionDraft)) == 0
    row = await session.scalar(select(context["api"]["model"]).where(context["api"]["model"].run_id == context["run_id"]))
    assert row is not None
    assert row.status == "issued"


@pytest.mark.asyncio
async def test_handler_mismatch_is_rejected_before_consume(session: AsyncSession, seeded_session):
    context = await _capability_context(session, seeded_session)
    api = context["api"]

    with pytest.raises(api["verification_error"]):
        async with session.begin_nested():
            await api["service"](session).lock_and_verify_for_draft(
                capability_ref=context["grant"].capability_ref,
                tenant_id=context["tenant_id"],
                actor_id=context["actor_id"],
                run_id=context["run_id"],
                target_merchant_id=context["target_merchant_id"],
                canonical_action="issue_coupon",
                action_payload_hash=context["action_payload_hash"],
                safety_snapshot_ref=context["snapshot_ref"],
                safety_snapshot_hash=context["snapshot_hash"],
                risk_decision_ref=context["risk_decision_ref"],
                risk_decision=context["risk_decision"],
                handler="execute_coupon_grant",
            )

    assert await session.scalar(select(func.count()).select_from(ActionDraft)) == 0


@pytest.mark.asyncio
async def test_consume_is_one_use_with_exact_idempotent_retry_and_distinct_audit_source(
    session: AsyncSession,
    seeded_session,
):
    context = await _capability_context(session, seeded_session)
    service = ActionService(session)

    first = await service.create_coupon_grant_draft(**_draft_kwargs(context))
    second = await service.create_coupon_grant_draft(**_draft_kwargs(context))

    assert first["status"] == second["status"] == "success"
    assert first["data"]["draft_id"] == second["data"]["draft_id"]
    assert first["data"]["created"] is True
    assert second["data"]["created"] is False
    assert second["data"]["idempotent_reused"] is True
    assert await session.scalar(select(func.count()).select_from(ActionDraft)) == 1
    events = (
        await session.execute(
            select(AgentTraceEvent).where(
                AgentTraceEvent.run_id == context["run_id"],
                AgentTraceEvent.event_type == "action_draft_created",
            )
        )
    ).scalars().all()
    assert len(events) == 1
    assert events[0].redacted_payload["authorization_source"] == "auto_allow_capability"
    row = await session.scalar(select(context["api"]["model"]).where(context["api"]["model"].run_id == context["run_id"]))
    assert row is not None
    assert row.status == "consumed"
    assert str(row.resulting_draft_id) == first["data"]["draft_id"]
    assert row.idempotency_key == first["data"]["idempotency_key"]


@pytest.mark.asyncio
async def test_consumed_capability_wrong_retry_binding_returns_zero_new_drafts(
    session: AsyncSession,
    seeded_session,
):
    context = await _capability_context(session, seeded_session)
    service = ActionService(session)
    first = await service.create_coupon_grant_draft(**_draft_kwargs(context))

    wrong_risk = dict(context["risk_decision"])
    wrong_risk["risk_reason"] = "tampered"
    replay = await service.create_coupon_grant_draft(**_draft_kwargs(context, risk_decision=wrong_risk))

    assert first["status"] == "success"
    assert replay["status"] == "error"
    assert await session.scalar(select(func.count()).select_from(ActionDraft)) == 1


@pytest.mark.asyncio
async def test_consumed_capability_idempotency_identity_tamper_closes_retry(
    session: AsyncSession,
    seeded_session,
):
    context = await _capability_context(session, seeded_session)
    service = ActionService(session)
    first = await service.create_coupon_grant_draft(**_draft_kwargs(context))
    row = await session.scalar(
        select(context["api"]["model"]).where(context["api"]["model"].run_id == context["run_id"])
    )
    assert row is not None
    row.idempotency_key = "tampered-idempotency-identity"
    await session.flush()

    replay = await service.create_coupon_grant_draft(**_draft_kwargs(context))

    assert first["status"] == "success"
    assert replay["status"] == "error"
    assert replay["error"]["error_code"] == "AUTO_ACTION_CAPABILITY_REPLAY"
    assert await session.scalar(select(func.count()).select_from(ActionDraft)) == 1


@pytest.mark.asyncio
async def test_expired_capability_is_closed_and_creates_zero_drafts(session: AsyncSession, seeded_session):
    context = await _capability_context(session, seeded_session)
    row = await session.scalar(select(context["api"]["model"]).where(context["api"]["model"].run_id == context["run_id"]))
    assert row is not None
    now = datetime.now(UTC)
    row.issued_at = now - timedelta(seconds=10)
    row.expires_at = now - timedelta(seconds=1)
    await session.flush()

    result = await ActionService(session).create_coupon_grant_draft(**_draft_kwargs(context))

    assert result["status"] == "error"
    assert result["error"]["error_code"] == "AUTO_ACTION_CAPABILITY_EXPIRED"
    assert await session.scalar(select(func.count()).select_from(ActionDraft)) == 0
    await session.refresh(row)
    assert row.status == "expired"


@pytest.mark.asyncio
@pytest.mark.parametrize("failure_point", ["after_draft", "after_consume", "after_event"])
async def test_write_failure_rolls_back_capability_draft_and_critical_event(
    session: AsyncSession,
    seeded_session,
    monkeypatch,
    failure_point: str,
):
    context = await _capability_context(session, seeded_session)
    service = ActionService(session)

    if failure_point == "after_draft":
        original = service.draft_store.create_or_get

        async def fail_after_draft(**kwargs):
            await original(**kwargs)
            raise RuntimeError("injected after draft")

        monkeypatch.setattr(service.draft_store, "create_or_get", fail_after_draft)
    elif failure_point == "after_consume":
        original = service.capability_service.mark_consumed

        async def fail_after_consume(*args, **kwargs):
            await original(*args, **kwargs)
            raise RuntimeError("injected after consume")

        monkeypatch.setattr(service.capability_service, "mark_consumed", fail_after_consume)
    else:
        original = service._emit_action_draft_created

        async def fail_after_event(**kwargs):
            await original(**kwargs)
            raise RuntimeError("injected after event")

        monkeypatch.setattr(service, "_emit_action_draft_created", fail_after_event)

    result = await service.create_coupon_grant_draft(**_draft_kwargs(context))

    assert result["status"] == "error"
    session.expire_all()
    assert await session.scalar(select(func.count()).select_from(ActionDraft)) == 0
    assert await session.scalar(select(func.count()).select_from(AgentTraceEvent)) == 0
    row = await session.scalar(select(context["api"]["model"]).where(context["api"]["model"].run_id == context["run_id"]))
    assert row is not None
    assert row.status == "issued"
    assert row.resulting_draft_id is None


@pytest.mark.asyncio
async def test_concurrent_consume_creates_one_draft_and_returns_same_identity(test_engine, seeded_session):
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as setup_session:
        context = await _capability_context(setup_session, seeded_session, commit=True)

    async def consume() -> dict[str, Any]:
        async with session_factory() as worker_session:
            result = await ActionService(worker_session).create_coupon_grant_draft(**_draft_kwargs(context))
            await worker_session.commit()
            return result

    first, second = await asyncio.gather(consume(), consume())

    assert first["status"] == second["status"] == "success"
    assert first["data"]["draft_id"] == second["data"]["draft_id"]
    assert sorted([first["data"]["created"], second["data"]["created"]]) == [False, True]
    async with session_factory() as verify_session:
        assert await verify_session.scalar(select(func.count()).select_from(ActionDraft)) == 1
        assert (
            await verify_session.scalar(
                select(func.count()).select_from(AgentTraceEvent).where(
                    AgentTraceEvent.run_id == context["run_id"],
                    AgentTraceEvent.event_type == "action_draft_created",
                )
            )
        ) == 1
