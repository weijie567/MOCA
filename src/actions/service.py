from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.actions.drafts import ActionDraftStore
from src.actions.schemas import ActionDraftV2Data, DraftOutcomeV1
from src.agent.events import emit_event
from src.agent.run_scope import BUSINESS_MERCHANT, UNKNOWN_LEGACY
from src.approvals.schemas import AutoAllowedActionBindingV1, RiskDecisionV1, TargetMerchantBindingV1
from src.approvals.snapshot_service import compute_action_payload_hash
from src.common.canonical_hash import CanonicalHashError
from src.db.models import ActionSafetySnapshot, AgentRun, ApprovalRequest
from src.knowledge.schemas import EvidenceRefV1
from src.tools.contracts import BusinessFactRefV1

_IDEMPOTENCY_CONFLICTS = {"idempotency_key_conflict", "idempotency_binding_conflict"}
_ACTION_RESULT_COMPAT_GATE = (
    "Phase 14 deprecated compatibility output; replace/remove at Phase 15 Replay Event Contract "
    "before Phase 15 verification, target no later than 2026-07-16 unless Phase 15 is replanned."
)


@dataclass(frozen=True)
class _ValidatedActionBinding:
    revision_marker: str
    approval_revision_ref: str | None
    target_merchant_id: str | None = None
    target_merchant_ref: dict[str, Any] | None = None
    business_fact_refs: list[dict[str, Any]] | None = None
    verified_evidence_refs: list[dict[str, Any]] | None = None
    claim_verification_ref: str | None = None
    claim_verification_summary: dict[str, Any] | None = None
    risk_decision_ref: str | None = None
    risk_decision: dict[str, Any] | None = None
    auto_allowed_binding_ref: str | None = None


def _tool_success(data: dict[str, Any]) -> dict[str, Any]:
    return {"status": "success", "data": data, "error": {}}


def _tool_error(error_code: str, message: str, retryable: bool) -> dict[str, Any]:
    return {
        "status": "error",
        "data": {},
        "error": {"error_code": error_code, "message": message, "retryable": retryable},
    }


class ActionService:
    """Business owner for durable action draft creation."""

    def __init__(self, session: AsyncSession, *, draft_store: ActionDraftStore | None = None) -> None:
        self.session = session
        self.draft_store = draft_store or ActionDraftStore(session)

    async def create_coupon_grant_draft(
        self,
        *,
        tenant_id: str,
        user_id: str,
        run_id: str,
        approval_request_id: str | None,
        idempotency_key: str,
        action_type: str,
        payload: dict[str, Any],
        action_payload_hash: str | None = None,
        safety_snapshot_ref: str | None = None,
        safety_snapshot_hash: str | None = None,
        target_merchant_id: str | None = None,
        target_merchant_ref: dict[str, Any] | None = None,
        business_fact_refs: list[dict[str, Any]] | None = None,
        verified_evidence_refs: list[dict[str, Any]] | None = None,
        claim_verification_ref: str | None = None,
        claim_verification_summary: dict[str, Any] | None = None,
        risk_decision_ref: str | None = None,
        risk_decision: dict[str, Any] | None = None,
        auto_allowed_binding: dict[str, Any] | None = None,
        thread_id: str | None = None,
        trace_id: str | None = None,
    ) -> dict[str, Any]:
        del user_id
        try:
            run_uuid = UUID(run_id)
            tenant_uuid = UUID(tenant_id)
            approval_uuid = UUID(approval_request_id) if approval_request_id else None
        except (AttributeError, TypeError, ValueError):
            return _tool_error("INVALID_REQUEST", "Action draft request is invalid", retryable=False)

        if not action_payload_hash or not safety_snapshot_ref or not safety_snapshot_hash:
            return _tool_error("ACTION_BINDING_REQUIRED", "Action draft requires exact safety binding", retryable=False)

        target_id = _target_id(payload)
        if target_id is None:
            return _tool_error("TARGET_ID_REQUIRED", "Action draft target_id is required", retryable=False)
        try:
            computed_payload_hash = compute_action_payload_hash(payload)
        except (CanonicalHashError, TypeError, ValueError):
            return _tool_error(
                "ACTION_BINDING_MISMATCH",
                "Action draft payload does not match approved safety binding",
                retryable=False,
            )
        if computed_payload_hash != action_payload_hash or str(payload.get("action_type") or "") != action_type:
            return _tool_error(
                "ACTION_BINDING_MISMATCH",
                "Action draft payload does not match approved safety binding",
                retryable=False,
            )

        try:
            async with self.session.begin_nested():
                binding = await self._validate_action_binding(
                    tenant_id=tenant_uuid,
                    run_id=run_uuid,
                    approval_request_id=approval_uuid,
                    action_payload_hash=action_payload_hash,
                    safety_snapshot_ref=safety_snapshot_ref,
                    safety_snapshot_hash=safety_snapshot_hash,
                    target_merchant_id=target_merchant_id,
                    target_merchant_ref=target_merchant_ref,
                    business_fact_refs=business_fact_refs,
                    verified_evidence_refs=verified_evidence_refs,
                    claim_verification_ref=claim_verification_ref,
                    claim_verification_summary=claim_verification_summary,
                    risk_decision_ref=risk_decision_ref,
                    risk_decision=risk_decision,
                    auto_allowed_binding=auto_allowed_binding,
                )
                if isinstance(binding, dict):
                    return binding
                idempotency_key = _build_idempotency_key(
                    tenant_id=tenant_uuid,
                    run_id=run_uuid,
                    revision_marker=binding.revision_marker,
                    action_type=action_type,
                    target_id=target_id,
                    action_payload_hash=action_payload_hash,
                )
                draft, created = await self.draft_store.create_or_get(
                    run_id=run_uuid,
                    tenant_id=tenant_uuid,
                    approval_request_id=approval_uuid,
                    idempotency_key=idempotency_key,
                    action_type=action_type,
                    target_id=target_id,
                    approval_revision_ref=binding.approval_revision_ref,
                    action_payload_hash=action_payload_hash,
                    safety_snapshot_ref=safety_snapshot_ref,
                    safety_snapshot_hash=safety_snapshot_hash,
                    payload=payload,
                    target_merchant_id=binding.target_merchant_id,
                    target_merchant_ref=binding.target_merchant_ref,
                    business_fact_refs=binding.business_fact_refs or [],
                    verified_evidence_refs=binding.verified_evidence_refs or [],
                    claim_verification_ref=binding.claim_verification_ref,
                    claim_verification_summary=binding.claim_verification_summary,
                    risk_decision_ref=binding.risk_decision_ref,
                    risk_decision=binding.risk_decision,
                    auto_allowed_binding_ref=binding.auto_allowed_binding_ref,
                    draft_outcome=_draft_outcome(
                        tenant_id=tenant_uuid,
                        run_id=run_uuid,
                        draft_id=None,
                    ),
                    execution_mode="demo",
                    draft_version=1,
                    lifecycle_status="active",
                    retention_policy="phase14_demo_draft",
                )
                draft_outcome = _draft_outcome_from_draft(draft)
                draft.draft_outcome = draft_outcome
                if created:
                    await self._emit_action_draft_created(
                        run_id=run_uuid,
                        tenant_id=tenant_uuid,
                        thread_id=thread_id,
                        trace_id=trace_id,
                        draft_id=draft.id,
                        target_id=target_id,
                        action_type=action_type,
                        action_payload_hash=action_payload_hash,
                        safety_snapshot_hash=safety_snapshot_hash,
                        draft_outcome=draft_outcome,
                    )
            return _tool_success(
                {
                    "draft_id": str(draft.id),
                    "idempotency_key": draft.idempotency_key,
                    "status": draft.status,
                    "created": created,
                    "idempotent_reused": not created,
                    "action_draft": _action_draft_data(draft),
                    "draft_outcome": draft_outcome,
                    "execution_mode": draft.execution_mode,
                    "action_result": _compat_action_result(draft, draft_outcome),
                }
            )
        except ValueError as exc:
            if str(exc) in _IDEMPOTENCY_CONFLICTS:
                return _tool_error(
                    "IDEMPOTENCY_CONFLICT",
                    "Action draft idempotency binding conflicts with an existing draft",
                    retryable=False,
                )
            return _tool_error("INVALID_REQUEST", "Action draft request is invalid", retryable=False)
        except Exception:
            return _tool_error("DRAFT_CREATION_FAILED", "Action draft creation failed", retryable=True)

    async def _validate_action_binding(
        self,
        *,
        tenant_id: UUID,
        run_id: UUID,
        approval_request_id: UUID | None,
        action_payload_hash: str,
        safety_snapshot_ref: str,
        safety_snapshot_hash: str,
        target_merchant_id: str | None,
        target_merchant_ref: dict[str, Any] | None,
        business_fact_refs: list[dict[str, Any]] | None,
        verified_evidence_refs: list[dict[str, Any]] | None,
        claim_verification_ref: str | None,
        claim_verification_summary: dict[str, Any] | None,
        risk_decision_ref: str | None,
        risk_decision: dict[str, Any] | None,
        auto_allowed_binding: dict[str, Any] | None,
    ) -> _ValidatedActionBinding | dict[str, Any]:
        snapshot = (
            await self.session.execute(
                select(ActionSafetySnapshot).where(
                    ActionSafetySnapshot.tenant_id == tenant_id,
                    ActionSafetySnapshot.run_id == run_id,
                    ActionSafetySnapshot.snapshot_ref == safety_snapshot_ref,
                    ActionSafetySnapshot.immutable_hash == safety_snapshot_hash,
                    ActionSafetySnapshot.action_payload_hash == action_payload_hash,
                    ActionSafetySnapshot.deleted_at.is_(None),
                )
            )
        ).scalar_one_or_none()
        if snapshot is None:
            return _tool_error("ACTION_BINDING_MISMATCH", "Action safety snapshot binding is invalid", retryable=False)

        requested_binding = _binding_material(
            target_merchant_id=target_merchant_id,
            target_merchant_ref=target_merchant_ref,
            business_fact_refs=business_fact_refs,
            verified_evidence_refs=verified_evidence_refs,
            claim_verification_ref=claim_verification_ref,
            claim_verification_summary=claim_verification_summary,
            risk_decision_ref=risk_decision_ref,
            risk_decision=risk_decision,
        )
        run = (
            await self.session.execute(
                select(AgentRun).where(
                    AgentRun.id == run_id,
                    AgentRun.tenant_id == tenant_id,
                )
            )
        ).scalar_one_or_none()
        if not _snapshot_phase36_binding_matches(snapshot, requested_binding):
            return _tool_error(
                "SNAPSHOT_BINDING_MISMATCH",
                "Action safety snapshot target binding is invalid",
                retryable=False,
            )
        if approval_request_id is None:
            validated = self._validate_auto_allowed_binding(
                tenant_id=tenant_id,
                run_id=run_id,
                action_payload_hash=action_payload_hash,
                safety_snapshot_ref=safety_snapshot_ref,
                safety_snapshot_hash=safety_snapshot_hash,
                requested_binding=requested_binding,
                auto_allowed_binding=auto_allowed_binding,
            )
            if isinstance(validated, dict):
                return validated
            run_matches, run_error = await _ensure_run_scope_matches_target(
                self.session,
                run,
                requested_binding=requested_binding,
            )
            if not run_matches:
                return _tool_error(
                    run_error or "RUN_SCOPE_BINDING_MISMATCH",
                    "Action target merchant does not match run scope",
                    retryable=False,
                )
            return validated

        run_matches, run_error = _run_scope_matches_target(run, requested_binding["target_merchant_id"])
        if not run_matches:
            return _tool_error(
                run_error or "RUN_SCOPE_BINDING_MISMATCH",
                "Action target merchant does not match run scope",
                retryable=False,
            )

        approval = (
            await self.session.execute(
                select(ApprovalRequest).where(
                    ApprovalRequest.id == approval_request_id,
                    ApprovalRequest.tenant_id == tenant_id,
                    ApprovalRequest.run_id == run_id,
                )
            )
        ).scalar_one_or_none()
        if approval is None:
            return _tool_error("APPROVAL_NOT_FOUND", "Approved request was not found", retryable=False)
        if (
            approval.legacy_non_executable
            or approval.schema_version != "approval_request.v2"
            or approval.status != "approved"
            or approval.action_payload_hash != action_payload_hash
            or approval.safety_snapshot_ref != safety_snapshot_ref
            or approval.safety_snapshot_hash != safety_snapshot_hash
        ):
            return _tool_error("APPROVAL_BINDING_MISMATCH", "Approved request binding is invalid", retryable=False)
        if not _approval_phase34_binding_matches(approval, requested_binding):
            return _tool_error("APPROVAL_BINDING_MISMATCH", "Approved request binding is invalid", retryable=False)
        return _ValidatedActionBinding(
            revision_marker=f"approval_revision_{approval.revision}",
            approval_revision_ref=f"approval_request/{approval.id}@rev{approval.revision}",
            **requested_binding,
        )

    def _validate_auto_allowed_binding(
        self,
        *,
        tenant_id: UUID,
        run_id: UUID,
        action_payload_hash: str,
        safety_snapshot_ref: str,
        safety_snapshot_hash: str,
        requested_binding: dict[str, Any],
        auto_allowed_binding: dict[str, Any] | None,
    ) -> _ValidatedActionBinding | dict[str, Any]:
        if not auto_allowed_binding:
            return _tool_error(
                "AUTO_ALLOWED_BINDING_REQUIRED",
                "No-approval action draft requires a durable auto-allowed binding",
                retryable=False,
            )
        try:
            trusted = AutoAllowedActionBindingV1.model_validate(auto_allowed_binding)
        except ValueError:
            return _tool_error(
                "AUTO_ALLOWED_BINDING_MISMATCH",
                "Auto-allowed action binding is invalid",
                retryable=False,
            )
        trusted_payload = trusted.model_dump(mode="json")
        risk_decision_ref = str(trusted.risk_decision_ref or "")
        if not risk_decision_ref:
            return _tool_error(
                "AUTO_ALLOWED_BINDING_MISMATCH",
                "Auto-allowed action binding is invalid",
                retryable=False,
            )
        expected = {
            "tenant_id": str(tenant_id),
            "run_id": str(run_id),
            "target_merchant_id": requested_binding.get("target_merchant_id"),
            "action_payload_hash": action_payload_hash,
            "safety_snapshot_ref": safety_snapshot_ref,
            "safety_snapshot_hash": safety_snapshot_hash,
            "risk_decision_ref": requested_binding.get("risk_decision_ref"),
            "business_fact_refs": requested_binding.get("business_fact_refs") or [],
            "verified_evidence_refs": requested_binding.get("verified_evidence_refs") or [],
            "claim_verification_ref": requested_binding.get("claim_verification_ref"),
            "claim_verification_summary": requested_binding.get("claim_verification_summary"),
        }
        actual = {key: trusted_payload.get(key) for key in expected}
        if actual != expected:
            return _tool_error(
                "AUTO_ALLOWED_BINDING_MISMATCH",
                "Auto-allowed action binding is invalid",
                retryable=False,
            )
        risk_decision = requested_binding.get("risk_decision")
        if (
            risk_decision is None
            or risk_decision.get("tenant_id") != str(tenant_id)
            or risk_decision.get("run_id") != str(run_id)
            or risk_decision.get("action_payload_hash") != action_payload_hash
            or risk_decision.get("approval_required") is not False
            or risk_decision_ref != requested_binding.get("risk_decision_ref")
        ):
            return _tool_error(
                "AUTO_ALLOWED_BINDING_MISMATCH",
                "Auto-allowed action binding is invalid",
                retryable=False,
            )
        revision_marker = f"auto_allowed:{risk_decision_ref}"
        return _ValidatedActionBinding(
            revision_marker=revision_marker,
            approval_revision_ref=revision_marker,
            auto_allowed_binding_ref=revision_marker,
            **requested_binding,
        )

    async def _emit_action_draft_created(
        self,
        *,
        run_id: UUID,
        tenant_id: UUID,
        thread_id: str | None,
        trace_id: str | None,
        draft_id: UUID,
        target_id: str,
        action_type: str,
        action_payload_hash: str,
        safety_snapshot_hash: str,
        draft_outcome: dict[str, Any],
    ) -> None:
        await emit_event(
            self.session,
            run_id=run_id,
            tenant_id=tenant_id,
            thread_id=thread_id or await _run_thread_id(self.session, run_id) or str(run_id),
            trace_id=trace_id,
            event_type="action_draft_created",
            actor={"type": "agent", "id": "moca"},
            resource_refs={
                "draft_id": str(draft_id),
                "target_id": target_id,
                "action_payload_hash": action_payload_hash,
                "safety_snapshot_hash": safety_snapshot_hash,
            },
            redacted_payload={
                "action_type": action_type,
                "execution_mode": "demo",
                "external_side_effect": False,
                "draft_outcome": DraftOutcomeV1.model_validate(draft_outcome).model_dump(mode="json"),
            },
        )


def _target_id(payload: dict[str, Any]) -> str | None:
    raw_target = payload.get("target_id")
    if raw_target is None:
        return None
    target = str(raw_target).strip()
    return target or None


async def _run_thread_id(session: AsyncSession, run_id: UUID) -> str | None:
    return (await session.execute(select(AgentRun.thread_id).where(AgentRun.id == run_id))).scalar_one_or_none()


def _run_scope_matches_target(run: AgentRun | None, requested_target_merchant_id: str | None) -> tuple[bool, str | None]:
    if run is None:
        return False, "RUN_SCOPE_MISSING"
    if run.scope_classification == BUSINESS_MERCHANT:
        if not requested_target_merchant_id or str(run.target_merchant_id) != str(requested_target_merchant_id):
            return False, "RUN_SCOPE_BINDING_MISMATCH"
        return True, None
    if requested_target_merchant_id:
        return False, "RUN_SCOPE_NOT_BUSINESS_MERCHANT"
    return False, "RUN_SCOPE_NOT_BUSINESS_MERCHANT"


async def _ensure_run_scope_matches_target(
    session: AsyncSession,
    run: AgentRun | None,
    *,
    requested_binding: dict[str, Any],
) -> tuple[bool, str | None]:
    requested_target_merchant_id = requested_binding.get("target_merchant_id")
    matches, error = _run_scope_matches_target(run, requested_target_merchant_id)
    if matches or run is None:
        return matches, error
    if (
        run.scope_classification != UNKNOWN_LEGACY
        or run.target_merchant_id is not None
        or run.target_merchant_ref is not None
        or not requested_target_merchant_id
        or requested_binding.get("target_merchant_ref") is None
    ):
        return False, error

    run.scope_classification = BUSINESS_MERCHANT
    run.target_merchant_id = requested_target_merchant_id
    run.target_merchant_ref = requested_binding["target_merchant_ref"]
    run.scope_source = "auto_allowed_action_binding_v1"
    run.scope_reason_codes = []
    await session.flush()
    return True, None


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _build_idempotency_key(
    *,
    tenant_id: UUID,
    run_id: UUID,
    revision_marker: str,
    action_type: str,
    target_id: str,
    action_payload_hash: str,
) -> str:
    raw_key = f"{tenant_id}:{run_id}:{revision_marker}:{action_type}:{target_id}:{action_payload_hash}"
    if len(raw_key) <= 256:
        return raw_key
    digest = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
    shortened = f"{tenant_id}:{run_id}:{revision_marker}:key_sha256:{digest}"
    if len(shortened) <= 256:
        return shortened
    marker_hint = _revision_marker_hint(revision_marker)
    marker_digest = hashlib.sha256(revision_marker.encode("utf-8")).hexdigest()[:16]
    return f"{tenant_id}:{run_id}:{marker_hint}_sha256:{marker_digest}:key_sha256:{digest}"


def _revision_marker_hint(revision_marker: str) -> str:
    raw_hint = (revision_marker.split(":", 1)[0] or "revision")[:48]
    hint = "".join(char if char.isalnum() or char in {"_", "-"} else "_" for char in raw_hint)
    return hint or "revision"


def _binding_material(
    *,
    target_merchant_id: str | None,
    target_merchant_ref: dict[str, Any] | None,
    business_fact_refs: list[dict[str, Any]] | None,
    verified_evidence_refs: list[dict[str, Any]] | None,
    claim_verification_ref: str | None,
    claim_verification_summary: dict[str, Any] | None,
    risk_decision_ref: str | None,
    risk_decision: dict[str, Any] | None,
) -> dict[str, Any]:
    return {
        "target_merchant_id": str(target_merchant_id) if target_merchant_id else None,
        "target_merchant_ref": _canonical_target_merchant_ref(target_merchant_ref),
        "business_fact_refs": _canonical_business_fact_refs(business_fact_refs),
        "verified_evidence_refs": _canonical_evidence_refs(verified_evidence_refs),
        "claim_verification_ref": str(claim_verification_ref) if claim_verification_ref else None,
        "claim_verification_summary": _json_safe(claim_verification_summary),
        "risk_decision_ref": str(risk_decision_ref) if risk_decision_ref else None,
        "risk_decision": _canonical_risk_decision(risk_decision),
    }


def _approval_phase34_binding_matches(approval: ApprovalRequest, requested: dict[str, Any]) -> bool:
    if approval.target_merchant_id != requested["target_merchant_id"]:
        return False
    if _canonical_target_merchant_ref(approval.target_merchant_ref) != requested["target_merchant_ref"]:
        return False
    if _canonical_business_fact_refs(approval.business_fact_refs) != requested["business_fact_refs"]:
        return False
    if _canonical_evidence_refs(approval.verified_evidence_refs) != requested["verified_evidence_refs"]:
        return False
    claim_requested = bool(requested["claim_verification_ref"] or requested["claim_verification_summary"])
    claim_approval = bool(approval.claim_verification_ref or approval.claim_verification_summary)
    if claim_requested or claim_approval:
        claim_ref_matches = approval.claim_verification_ref == requested["claim_verification_ref"]
        claim_summary_matches = _json_safe(approval.claim_verification_summary) == requested["claim_verification_summary"]
        if not (claim_ref_matches or claim_summary_matches):
            return False
    risk_requested = bool(requested["risk_decision_ref"] or requested["risk_decision"])
    risk_approval = bool(approval.risk_decision_ref or approval.risk_decision)
    if risk_requested or risk_approval:
        risk_ref_matches = approval.risk_decision_ref == requested["risk_decision_ref"]
        risk_payload_matches = _canonical_risk_decision(approval.risk_decision) == requested["risk_decision"]
        if not (risk_ref_matches or risk_payload_matches):
            return False
    return True


def _snapshot_phase36_binding_matches(snapshot: ActionSafetySnapshot, requested: dict[str, Any]) -> bool:
    if snapshot.action_payload_hash is None:
        return True
    if snapshot.target_merchant_id != requested["target_merchant_id"]:
        return False
    if _canonical_target_merchant_ref(snapshot.target_merchant_ref) != requested["target_merchant_ref"]:
        return False
    if _canonical_business_fact_refs(snapshot.business_fact_refs) != requested["business_fact_refs"]:
        return False
    return True


def _canonical_target_merchant_ref(value: dict[str, Any] | None) -> dict[str, Any] | None:
    if value is None:
        return None
    return TargetMerchantBindingV1.model_validate(_contract_json_safe(value)).model_dump(mode="json")


def _canonical_business_fact_refs(value: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    return [
        BusinessFactRefV1.model_validate(_contract_json_safe(ref)).model_dump(mode="json") for ref in value or []
    ]


def _canonical_evidence_refs(value: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    return [EvidenceRefV1.model_validate(_contract_json_safe(ref)).model_dump(mode="json") for ref in value or []]


def _canonical_risk_decision(value: dict[str, Any] | None) -> dict[str, Any] | None:
    if value is None:
        return None
    return RiskDecisionV1.model_validate(_contract_json_safe(value)).model_dump(mode="json")


def _json_safe_list(value: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    safe = _json_safe(value)
    return safe if isinstance(safe, list) else []


def _contract_json_safe(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, list):
        return [_contract_json_safe(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _contract_json_safe(item) for key, item in value.items()}
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def _json_safe(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json", exclude_none=True)
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items() if item is not None}
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def _draft_outcome(*, tenant_id: UUID, run_id: UUID, draft_id: UUID | None) -> dict[str, Any]:
    return DraftOutcomeV1(
        tenant_id=str(tenant_id),
        run_id=str(run_id),
        draft_id=str(draft_id) if draft_id is not None else None,
        created_at=_now_iso(),
    ).model_dump(mode="json")


def _draft_outcome_from_draft(draft) -> dict[str, Any]:
    outcome = dict(draft.draft_outcome or {})
    if not outcome:
        outcome = _draft_outcome(tenant_id=draft.tenant_id, run_id=draft.run_id, draft_id=draft.id)
    else:
        outcome["draft_id"] = str(draft.id)
    return DraftOutcomeV1.model_validate(outcome).model_dump(mode="json")


def _action_draft_data(draft) -> dict[str, Any]:
    data = {
        "schema_version": draft.schema_version,
        "tenant_id": str(draft.tenant_id),
        "run_id": str(draft.run_id),
        "draft_id": str(draft.id),
        "proposed_action": draft.payload,
        "approval_revision_ref": draft.approval_revision_ref,
        "approval_ref": str(draft.approval_request_id) if draft.approval_request_id else None,
        "action_payload_hash": draft.action_payload_hash,
        "safety_snapshot_ref": draft.safety_snapshot_ref,
        "safety_snapshot_hash": draft.safety_snapshot_hash,
        "target_id": draft.target_id,
        "target_merchant_id": draft.target_merchant_id,
        "target_merchant_ref": _json_safe(draft.target_merchant_ref),
        "business_fact_refs": list(draft.business_fact_refs or []),
        "verified_evidence_refs": list(draft.verified_evidence_refs or []),
        "claim_verification_ref": draft.claim_verification_ref,
        "claim_verification_summary": _json_safe(draft.claim_verification_summary),
        "risk_decision_ref": draft.risk_decision_ref,
        "risk_decision": _json_safe(draft.risk_decision),
        "auto_allowed_binding_ref": draft.auto_allowed_binding_ref,
        "idempotency_key": draft.idempotency_key,
        "status": draft.status,
        "execution_mode": draft.execution_mode,
        "draft_version": draft.draft_version,
        "lifecycle_status": draft.lifecycle_status,
        "retention_policy": draft.retention_policy,
        "draft_outcome": _draft_outcome_from_draft(draft),
        "created_at": draft.created_at.isoformat() if draft.created_at else None,
    }
    return ActionDraftV2Data.model_validate(data).model_dump(mode="json")


def _compat_action_result(draft, draft_outcome: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": "draft_created",
        "data": {
            "draft_id": str(draft.id),
            "draft_outcome": draft_outcome,
        },
        "error": {},
        "compatibility": _ACTION_RESULT_COMPAT_GATE,
    }


async def create_coupon_grant_draft(
    *,
    tenant_id: str,
    user_id: str,
    run_id: str,
    approval_request_id: str | None,
    idempotency_key: str,
    action_type: str,
    payload: dict[str, Any],
    session: AsyncSession,
    action_payload_hash: str | None = None,
    safety_snapshot_ref: str | None = None,
    safety_snapshot_hash: str | None = None,
    target_merchant_id: str | None = None,
    target_merchant_ref: dict[str, Any] | None = None,
    business_fact_refs: list[dict[str, Any]] | None = None,
    verified_evidence_refs: list[dict[str, Any]] | None = None,
    claim_verification_ref: str | None = None,
    claim_verification_summary: dict[str, Any] | None = None,
    risk_decision_ref: str | None = None,
    risk_decision: dict[str, Any] | None = None,
    auto_allowed_binding: dict[str, Any] | None = None,
    thread_id: str | None = None,
    trace_id: str | None = None,
) -> dict[str, Any]:
    """Compatibility function for old call sites."""

    return await ActionService(session).create_coupon_grant_draft(
        tenant_id=tenant_id,
        user_id=user_id,
        run_id=run_id,
        approval_request_id=approval_request_id,
        idempotency_key=idempotency_key,
        action_type=action_type,
        payload=payload,
        action_payload_hash=action_payload_hash,
        safety_snapshot_ref=safety_snapshot_ref,
        safety_snapshot_hash=safety_snapshot_hash,
        target_merchant_id=target_merchant_id,
        target_merchant_ref=target_merchant_ref,
        business_fact_refs=business_fact_refs,
        verified_evidence_refs=verified_evidence_refs,
        claim_verification_ref=claim_verification_ref,
        claim_verification_summary=claim_verification_summary,
        risk_decision_ref=risk_decision_ref,
        risk_decision=risk_decision,
        auto_allowed_binding=auto_allowed_binding,
        thread_id=thread_id,
        trace_id=trace_id,
    )
