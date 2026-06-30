"""Package-owned approval persistence helpers for the v2 state machine."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.approvals.snapshots import ActionSafetySnapshot as ActionSafetySnapshotContract
from src.db.models import (
    ActionSafetySnapshot as ActionSafetySnapshotRow,
)
from src.db.models import (
    ApprovalAssignment,
    ApprovalDecision,
    ApprovalEvent,
    ApprovalLevel,
    ApprovalRequest,
)


class ApprovalRepositoryConflict(ValueError):
    """Raised when expected approval versions or bindings do not match."""


class ApprovalRepository:
    """SQLAlchemy repository used only by ``src.approvals`` services."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def lock_request(self, approval_id: UUID, tenant_id: UUID) -> ApprovalRequest | None:
        stmt = (
            select(ApprovalRequest)
            .where(
                ApprovalRequest.id == approval_id,
                ApprovalRequest.tenant_id == tenant_id,
            )
            .with_for_update()
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def lock_current_level(self, request_id: UUID) -> ApprovalLevel | None:
        stmt = (
            select(ApprovalLevel)
            .where(
                ApprovalLevel.approval_request_id == request_id,
                ApprovalLevel.status == "pending",
                ApprovalLevel.deleted_at.is_(None),
            )
            .order_by(ApprovalLevel.level_number.asc())
            .with_for_update()
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def lock_assignment(self, assignment_id: UUID, level_id: UUID) -> ApprovalAssignment | None:
        stmt = (
            select(ApprovalAssignment)
            .where(
                ApprovalAssignment.id == assignment_id,
                ApprovalAssignment.approval_level_id == level_id,
                ApprovalAssignment.deleted_at.is_(None),
            )
            .with_for_update()
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def lock_assignment_by_level(self, level_id: UUID) -> ApprovalAssignment | None:
        stmt = (
            select(ApprovalAssignment)
            .where(
                ApprovalAssignment.approval_level_id == level_id,
                ApprovalAssignment.status == "pending",
                ApprovalAssignment.deleted_at.is_(None),
            )
            .order_by(ApprovalAssignment.created_at.asc())
            .with_for_update()
        )
        return (await self.session.execute(stmt)).scalars().first()

    async def create_snapshot_row(
        self,
        snapshot: ActionSafetySnapshotContract,
        *,
        created_by: UUID | None = None,
    ) -> ActionSafetySnapshotRow:
        existing = await self.get_snapshot_by_hash(
            tenant_id=UUID(snapshot.tenant_id),
            immutable_hash=snapshot.immutable_hash,
        )
        if existing is not None:
            return existing

        row = ActionSafetySnapshotRow(
            tenant_id=UUID(snapshot.tenant_id),
            run_id=UUID(snapshot.run_id),
            snapshot_ref=snapshot.snapshot_ref,
            snapshot_json=snapshot.model_dump(mode="json"),
            immutable_hash=snapshot.immutable_hash,
            action_payload_hash=snapshot.action_payload_hash,
            target_merchant_id=snapshot.target_merchant_id,
            target_merchant_ref=snapshot.target_merchant_ref.model_dump(mode="json") if snapshot.target_merchant_ref else None,
            business_fact_refs=[ref.model_dump(mode="json") for ref in snapshot.business_fact_refs],
            policy_config_version=snapshot.policy_config_version,
            risk_config_version=snapshot.risk_config_version,
            retrieval_config_version=snapshot.retrieval_config_version,
            created_by=created_by,
        )
        self.session.add(row)
        await self.session.flush()
        return row

    async def get_snapshot_by_hash(
        self,
        *,
        tenant_id: UUID,
        immutable_hash: str,
    ) -> ActionSafetySnapshotRow | None:
        stmt = select(ActionSafetySnapshotRow).where(
            ActionSafetySnapshotRow.tenant_id == tenant_id,
            ActionSafetySnapshotRow.immutable_hash == immutable_hash,
            ActionSafetySnapshotRow.deleted_at.is_(None),
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_snapshot_by_ref_or_hash(
        self,
        *,
        tenant_id: UUID,
        safety_snapshot_ref: str,
        safety_snapshot_hash: str,
    ) -> ActionSafetySnapshotRow | None:
        stmt = select(ActionSafetySnapshotRow).where(
            ActionSafetySnapshotRow.tenant_id == tenant_id,
            ActionSafetySnapshotRow.snapshot_ref == safety_snapshot_ref,
            ActionSafetySnapshotRow.immutable_hash == safety_snapshot_hash,
            ActionSafetySnapshotRow.deleted_at.is_(None),
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def next_request_revision(self, tenant_id: UUID, run_id: UUID) -> int:
        max_revision = await self.session.scalar(
            select(func.max(ApprovalRequest.revision)).where(
                ApprovalRequest.tenant_id == tenant_id,
                ApprovalRequest.run_id == run_id,
            )
        )
        return int(max_revision or 0) + 1

    async def create_request_with_single_level(
        self,
        *,
        tenant_id: UUID,
        run_id: UUID,
        thread_id: str,
        requested_by: UUID,
        proposed_action: dict[str, Any],
        approval_policy_id: str,
        policy_version: str,
        risk_level: str,
        risk_rule_ref: str | None,
        action_payload_hash: str,
        safety_snapshot_ref: str,
        safety_snapshot_hash: str,
        expires_at: datetime,
        required_role: str,
        assigned_role: str,
        level_mode: str,
        sla_due_at: datetime,
        revision: int | None = None,
        risk_reason: str | None = None,
        target_merchant_id: str | None = None,
        target_merchant_ref: dict[str, Any] | None = None,
        business_fact_refs: list[dict[str, Any]] | None = None,
        verified_evidence_refs: list[dict[str, Any]] | None = None,
        claim_verification_ref: str | None = None,
        claim_verification_summary: dict[str, Any] | None = None,
        risk_decision_ref: str | None = None,
        risk_decision: dict[str, Any] | None = None,
        approval_idempotency_key: str | None = None,
    ) -> tuple[ApprovalRequest, ApprovalLevel, ApprovalAssignment, ApprovalEvent]:
        request_revision = revision or await self.next_request_revision(tenant_id, run_id)
        request = ApprovalRequest(
            tenant_id=tenant_id,
            run_id=run_id,
            thread_id=thread_id,
            schema_version="approval_request.v2",
            status="pending",
            approval_policy_id=approval_policy_id,
            policy_version=policy_version,
            revision=request_revision,
            version=1,
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
            approval_idempotency_key=approval_idempotency_key,
            legacy_non_executable=False,
            requested_by=requested_by,
            proposed_action=proposed_action,
            risk_level=risk_level,
            risk_rule_ref=risk_rule_ref,
            risk_reason=risk_reason,
            expires_at=expires_at,
        )
        self.session.add(request)
        await self.session.flush()

        level = ApprovalLevel(
            approval_request_id=request.id,
            schema_version="approval_level.v2",
            level_number=1,
            version=1,
            status="pending",
            required_role=required_role,
            mode=level_mode,
            sla_due_at=sla_due_at,
        )
        self.session.add(level)
        await self.session.flush()

        assignment = ApprovalAssignment(
            approval_level_id=level.id,
            schema_version="approval_assignment.v2",
            assigned_role=assigned_role,
            status="pending",
            version=1,
        )
        self.session.add(assignment)
        await self.session.flush()

        event = await self.insert_approval_event(
            request=request,
            event_type="approval_requested",
            actor_id=requested_by,
            level=level,
            assignment=assignment,
            metadata={
                "approval_policy_id": approval_policy_id,
                "policy_version": policy_version,
                "risk_level": risk_level,
                "risk_rule_ref": risk_rule_ref,
            },
            resource_refs={
                "action_payload_hash": action_payload_hash,
                "safety_snapshot_ref": safety_snapshot_ref,
                "safety_snapshot_hash": safety_snapshot_hash,
            },
        )
        return request, level, assignment, event

    @staticmethod
    def assert_request_versions(
        request: ApprovalRequest,
        *,
        expected_request_version: int,
        expected_revision: int,
    ) -> None:
        if request.version != expected_request_version or request.revision != expected_revision:
            raise ApprovalRepositoryConflict("approval_conflict")

    @staticmethod
    def assert_level_version(level: ApprovalLevel, *, expected_level_version: int) -> None:
        if level.version != expected_level_version:
            raise ApprovalRepositoryConflict("approval_conflict")

    @staticmethod
    def assert_assignment_version(
        assignment: ApprovalAssignment,
        *,
        expected_assignment_version: int,
    ) -> None:
        if assignment.version != expected_assignment_version:
            raise ApprovalRepositoryConflict("approval_conflict")

    async def insert_decision(
        self,
        *,
        request: ApprovalRequest,
        level: ApprovalLevel,
        assignment: ApprovalAssignment,
        actor_id: UUID,
        decision_type: str,
        reason: str | None = None,
        response_text: str | None = None,
        edited_action: dict[str, Any] | None = None,
    ) -> ApprovalDecision:
        decision = ApprovalDecision(
            approval_request_id=request.id,
            approval_level_id=level.id,
            approval_assignment_id=assignment.id,
            tenant_id=request.tenant_id,
            run_id=request.run_id,
            thread_id=request.thread_id,
            request_revision=request.revision,
            request_version=request.version,
            level_version=level.version,
            level_mode=level.mode,
            assignment_version=assignment.version,
            decision_type=decision_type,
            reason=reason,
            response_text=response_text,
            edited_action_json=edited_action,
            actor_id=actor_id,
        )
        self.session.add(decision)
        await self.session.flush()
        return decision

    async def insert_approval_event(
        self,
        *,
        request: ApprovalRequest,
        event_type: str,
        decision: ApprovalDecision | None = None,
        actor_id: UUID | None = None,
        level: ApprovalLevel | None = None,
        assignment: ApprovalAssignment | None = None,
        metadata: dict[str, Any] | None = None,
        resource_refs: dict[str, Any] | None = None,
        redacted_payload: dict[str, Any] | None = None,
    ) -> ApprovalEvent:
        safe_resource_refs = {
            "request_ref": f"approval_request:{request.id}:r{request.revision}",
            "revision_ref": f"approval_revision:{request.id}:r{request.revision}:v{request.version}",
            "request_version": request.version,
            "action_payload_hash": request.action_payload_hash,
            "safety_snapshot_ref": request.safety_snapshot_ref,
            "safety_snapshot_hash": request.safety_snapshot_hash,
            **(resource_refs or {}),
        }
        if level is not None:
            safe_resource_refs["level_ref"] = f"approval_level:{level.id}:v{level.version}"
            safe_resource_refs["level_version"] = level.version
        if assignment is not None:
            safe_resource_refs["assignment_ref"] = f"approval_assignment:{assignment.id}:v{assignment.version}"
            safe_resource_refs["assignment_version"] = assignment.version
        if decision is not None:
            safe_resource_refs["decision_ref"] = f"approval_decision:{decision.id}"

        event = ApprovalEvent(
            approval_request_id=request.id,
            approval_decision_id=decision.id if decision else None,
            tenant_id=request.tenant_id,
            run_id=request.run_id,
            thread_id=request.thread_id,
            request_revision=request.revision,
            request_version=request.version,
            level_version=level.version if level else None,
            assignment_version=assignment.version if assignment else None,
            actor_id=actor_id,
            event_type=event_type,
            metadata_json=metadata or {},
            resource_refs_json=safe_resource_refs,
            redacted_payload_json={"event_type": event_type, "status": request.status, **(redacted_payload or {})},
        )
        self.session.add(event)
        await self.session.flush()
        return event

    async def increment_request_version(self, request: ApprovalRequest, *, status: str | None = None) -> int:
        if status is not None:
            request.status = status
        request.version = int(request.version or 0) + 1
        await self.session.flush()
        return int(request.version)

    async def increment_level_version(self, level: ApprovalLevel, *, status: str | None = None) -> int:
        if status is not None:
            level.status = status
        level.version += 1
        await self.session.flush()
        return level.version

    async def increment_assignment_version(
        self,
        assignment: ApprovalAssignment,
        *,
        status: str | None = None,
    ) -> int:
        if status is not None:
            assignment.status = status
        assignment.version += 1
        await self.session.flush()
        return assignment.version
