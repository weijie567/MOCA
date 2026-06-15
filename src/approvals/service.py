"""ApprovalService owns approval state transitions and trusted resume payloads."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.approvals.events import (
    approval_revision_ref,
    emit_approval_decided,
    emit_approval_expired,
    emit_approval_requested,
)
from src.approvals.policy import ApprovalPolicy, ApprovalPolicyError
from src.approvals.repository import ApprovalRepository, ApprovalRepositoryConflict
from src.approvals.schemas import (
    ApprovalDecisionCommand,
    ApprovalDecisionResult,
    ApprovalInfoCommand,
    ApprovalInfoResult,
    ApprovalRequestCreateCommand,
    ApprovalRequestCreateResult,
    TrustedApprovalResultV1,
)
from src.approvals.snapshot_service import (
    ActionSafetySnapshotPersistenceError,
    persist_action_safety_snapshot,
)
from src.db.models import ApprovalAssignment, ApprovalLevel, ApprovalRequest
from src.knowledge.schemas import EvidenceRefV1, canonical_evidence_projection


class ApprovalTransitionError(ValueError):
    """Domain error mapped by API callers to stable approval responses."""

    def __init__(self, code: str, message: str | None = None) -> None:
        super().__init__(message or code)
        self.code = code


@dataclass(frozen=True)
class ApprovalDecisionContext:
    request: ApprovalRequest
    level: ApprovalLevel
    assignment: ApprovalAssignment


@dataclass(frozen=True)
class _SnapshotBinding:
    action_payload_hash: str
    safety_snapshot_ref: str
    safety_snapshot_hash: str


class ApprovalService:
    """State machine owner for executable v2 approval requests."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        repository: ApprovalRepository | None = None,
        policy: ApprovalPolicy | None = None,
    ) -> None:
        self.session = session
        self.repository = repository or ApprovalRepository(session)
        self.policy = policy or ApprovalPolicy()

    async def create_request(self, command: ApprovalRequestCreateCommand) -> ApprovalRequestCreateResult:
        self._assert_create_context(command)
        try:
            async with self.session.begin_nested():
                snapshot = await self._load_or_persist_snapshot(command)
                assignment_plan = self.policy.default_single_level_assignment(
                    now=command.created_at,
                    required_role=command.required_role,
                    mode=command.level_mode,
                )
                request, level, assignment, event = await self.repository.create_request_with_single_level(
                    tenant_id=command.tenant_id,
                    run_id=command.run_id,
                    thread_id=command.thread_id,
                    requested_by=command.requested_by,
                    proposed_action=command.proposed_action,
                    approval_policy_id=command.approval_policy_id,
                    policy_version=command.policy_version,
                    risk_level=command.risk_level,
                    risk_rule_ref=command.risk_rule_ref,
                    action_payload_hash=snapshot.action_payload_hash,
                    safety_snapshot_ref=snapshot.safety_snapshot_ref,
                    safety_snapshot_hash=snapshot.safety_snapshot_hash,
                    expires_at=command.expires_at,
                    required_role=assignment_plan.required_role,
                    assigned_role=assignment_plan.assigned_role,
                    level_mode=assignment_plan.mode,
                    sla_due_at=assignment_plan.sla_due_at,
                    risk_reason=command.risk_reason,
                )
                await emit_approval_requested(
                    self.session,
                    request=request,
                    level=level,
                    assignment=assignment,
                    actor_id=command.requested_by,
                    existing_event=event,
                )
                return ApprovalRequestCreateResult(
                    approval_id=request.id,
                    revision=request.revision,
                    request_version=request.version,
                    level_id=level.id,
                    level_version=level.version,
                    assignment_id=assignment.id,
                    assignment_version=assignment.version,
                    action_payload_hash=request.action_payload_hash,
                    safety_snapshot_ref=request.safety_snapshot_ref,
                    safety_snapshot_hash=request.safety_snapshot_hash,
                    graph_thread_id=request.thread_id,
                )
        except ActionSafetySnapshotPersistenceError as exc:
            raise ApprovalTransitionError("approval_not_executable", str(exc)) from exc

    async def get_request(self, approval_id: UUID, tenant_id: UUID) -> ApprovalRequest | None:
        stmt = select(ApprovalRequest).where(
            ApprovalRequest.id == approval_id,
            ApprovalRequest.tenant_id == tenant_id,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_pending_requests(self, tenant_id: UUID) -> list[ApprovalRequest]:
        stmt = (
            select(ApprovalRequest)
            .where(
                ApprovalRequest.tenant_id == tenant_id,
                ApprovalRequest.status == "pending",
                ApprovalRequest.expires_at > datetime.now(UTC),
            )
            .order_by(ApprovalRequest.created_at.desc())
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def get_decision_context(self, approval_id: UUID, tenant_id: UUID) -> ApprovalDecisionContext | None:
        request = await self.get_request(approval_id, tenant_id)
        if request is None:
            return None
        level = await self.repository.lock_current_level(request.id)
        if level is None:
            raise ApprovalTransitionError("approval_conflict")
        assignment_stmt = (
            select(ApprovalAssignment)
            .where(
                ApprovalAssignment.approval_level_id == level.id,
                ApprovalAssignment.status == "pending",
                ApprovalAssignment.deleted_at.is_(None),
            )
            .order_by(ApprovalAssignment.created_at.asc())
        )
        assignment = (await self.session.execute(assignment_stmt)).scalars().first()
        if assignment is None:
            raise ApprovalTransitionError("approval_conflict")
        return ApprovalDecisionContext(request=request, level=level, assignment=assignment)

    async def decide(self, command: ApprovalDecisionCommand) -> ApprovalDecisionResult:
        try:
            async with self.session.begin_nested():
                request = await self.repository.lock_request(command.approval_id, command.tenant_id)
                if request is None:
                    raise ApprovalTransitionError("approval_not_found")

                self._assert_executable_request(request)
                self._assert_request_binding(request, command)
                await self._assert_snapshot_binding(request)
                self._assert_hash_binding(request, command)
                self.repository.assert_request_versions(
                    request,
                    expected_request_version=command.expected_request_version,
                    expected_revision=command.expected_revision,
                )
                self._assert_pending_request(request)

                level = await self.repository.lock_current_level(request.id)
                if level is None or level.id != command.level_id:
                    raise ApprovalTransitionError("approval_conflict")
                self.repository.assert_level_version(
                    level,
                    expected_level_version=command.expected_level_version,
                )

                assignment = await self.repository.lock_assignment(command.assignment_id, level.id)
                if assignment is None:
                    raise ApprovalTransitionError("approval_conflict")
                self.repository.assert_assignment_version(
                    assignment,
                    expected_assignment_version=command.expected_assignment_version,
                )
                self._assert_assignment_can_transition(assignment)
                self.policy.assert_not_self_approval(
                    requested_by=request.requested_by,
                    actor_id=command.actor_id,
                )
                self.policy.assert_actor_can_review(
                    actor_role=command.actor_role,
                    assigned_role=assignment.assigned_role,
                )

                if command.decision_type in {"accept", "approve"}:
                    return await self._approve(command, request, level, assignment)
                if command.decision_type == "edit":
                    return await self._edit(command, request, level, assignment)
                if command.decision_type == "respond":
                    return await self._respond(command, request, level, assignment)
                if command.decision_type == "reject":
                    return await self._terminal_decision(command, request, level, assignment, status="rejected")
                if command.decision_type == "ignore":
                    return await self._terminal_decision(command, request, level, assignment, status="cancelled")
                raise ApprovalTransitionError("approval_invalid_decision")
        except ApprovalRepositoryConflict as exc:
            raise ApprovalTransitionError("approval_conflict") from exc
        except ApprovalPolicyError as exc:
            raise ApprovalTransitionError(exc.code, str(exc)) from exc

    async def attach_info(self, command: ApprovalInfoCommand) -> ApprovalInfoResult:
        try:
            async with self.session.begin_nested():
                request = await self.repository.lock_request(command.approval_id, command.tenant_id)
                if request is None:
                    raise ApprovalTransitionError("approval_not_found")

                self._assert_executable_request(request)
                self._assert_needs_info_request(request, command)
                await self._assert_snapshot_binding(request)
                self.repository.assert_request_versions(
                    request,
                    expected_request_version=command.expected_request_version,
                    expected_revision=command.expected_revision,
                )

                level = await self.repository.lock_current_level(request.id)
                if level is None:
                    raise ApprovalTransitionError("approval_conflict")
                self.repository.assert_level_version(
                    level,
                    expected_level_version=command.expected_level_version,
                )

                assignment = await self.repository.lock_assignment_by_level(level.id)
                if assignment is None:
                    raise ApprovalTransitionError("approval_conflict")
                self.repository.assert_assignment_version(
                    assignment,
                    expected_assignment_version=command.expected_assignment_version,
                )
                self._assert_assignment_can_transition(assignment)
                self.policy.assert_not_self_approval(
                    requested_by=request.requested_by,
                    actor_id=command.actor_id,
                )
                self.policy.assert_actor_can_review(
                    actor_role=command.actor_role,
                    assigned_role=assignment.assigned_role,
                )

                if self._info_changes_revision_material(command.info_payload):
                    return await self._supersede_from_info(command, request, level, assignment)
                return await self._revalidate_same_revision(command, request, level, assignment)
        except ApprovalRepositoryConflict as exc:
            raise ApprovalTransitionError("approval_conflict") from exc
        except ApprovalPolicyError as exc:
            raise ApprovalTransitionError(exc.code, str(exc)) from exc

    async def expire_due_request(
        self,
        approval_id: UUID,
        tenant_id: UUID,
        *,
        now: datetime | None = None,
    ) -> ApprovalRequest | None:
        current_time = now or datetime.now(UTC)
        async with self.session.begin_nested():
            request = await self.repository.lock_request(approval_id, tenant_id)
            if request is None or request.status != "pending" or request.expires_at > current_time:
                return None
            level = await self.repository.lock_current_level(request.id)
            assignment = await self.repository.lock_assignment_by_level(level.id) if level else None
            if assignment is not None:
                await self.repository.increment_assignment_version(assignment, status="expired")
            if level is not None:
                await self.repository.increment_level_version(level, status="expired")
            await self.repository.increment_request_version(request, status="expired")
            await emit_approval_expired(
                self.session,
                request=request,
                level=level,
                assignment=assignment,
                metadata={"reason": "sla_due"},
            )
            return request

    async def _load_or_persist_snapshot(self, command: ApprovalRequestCreateCommand) -> _SnapshotBinding:
        if command.safety_snapshot_ref and command.safety_snapshot_hash:
            if not command.action_payload_hash:
                raise ApprovalTransitionError("approval_not_executable")
            snapshot = await self.repository.get_snapshot_by_ref_or_hash(
                tenant_id=command.tenant_id,
                safety_snapshot_ref=command.safety_snapshot_ref,
                safety_snapshot_hash=command.safety_snapshot_hash,
            )
            if snapshot is None or snapshot.action_payload_hash != command.action_payload_hash:
                raise ApprovalTransitionError("approval_not_executable")
            return _SnapshotBinding(
                action_payload_hash=snapshot.action_payload_hash,
                safety_snapshot_ref=snapshot.snapshot_ref,
                safety_snapshot_hash=snapshot.immutable_hash,
            )

        snapshot = await persist_action_safety_snapshot(
            self.session,
            tenant_id=command.tenant_id,
            run_id=command.run_id,
            proposed_action=command.proposed_action,
            action_payload_hash=command.action_payload_hash,
            policy_config_version=command.policy_config_version,
            risk_config_version=command.risk_config_version,
            retrieval_config_version=command.retrieval_config_version,
            evidence_refs=command.evidence_refs,
            created_at=command.created_at,
            created_by=command.requested_by,
            repository=self.repository,
        )
        return _SnapshotBinding(
            action_payload_hash=snapshot.action_payload_hash,
            safety_snapshot_ref=snapshot.safety_snapshot_ref,
            safety_snapshot_hash=snapshot.safety_snapshot_hash,
        )

    async def _approve(
        self,
        command: ApprovalDecisionCommand,
        request: ApprovalRequest,
        level: ApprovalLevel,
        assignment: ApprovalAssignment,
    ) -> ApprovalDecisionResult:
        decision = await self.repository.insert_decision(
            request=request,
            level=level,
            assignment=assignment,
            actor_id=command.actor_id,
            decision_type=command.decision_type,
            reason=command.reason,
        )
        await self.repository.increment_assignment_version(assignment, status="approved")
        await self.repository.increment_level_version(level, status="approved")
        await self.repository.increment_request_version(request, status="approved")
        event = await emit_approval_decided(
            self.session,
            request=request,
            level=level,
            assignment=assignment,
            decision=decision,
            actor_id=command.actor_id,
            decision_type=command.decision_type,
        )
        return self._result(
            request=request,
            level=level,
            assignment=assignment,
            actor_id=command.actor_id,
            decision_id=decision.id,
            event_id=event.id,
            decision_type=command.decision_type,
            reason=command.reason,
        )

    async def _respond(
        self,
        command: ApprovalDecisionCommand,
        request: ApprovalRequest,
        level: ApprovalLevel,
        assignment: ApprovalAssignment,
    ) -> ApprovalDecisionResult:
        clarification_request_id = request.clarification_request_id or f"approval-clarify:{uuid4()}"
        old_revision_ref = approval_revision_ref(request)
        decision = await self.repository.insert_decision(
            request=request,
            level=level,
            assignment=assignment,
            actor_id=command.actor_id,
            decision_type=command.decision_type,
            reason=command.reason,
            response_text=command.response_text,
        )
        request.clarification_request_id = clarification_request_id
        await self.repository.increment_assignment_version(assignment)
        await self.repository.increment_level_version(level)
        await self.repository.increment_request_version(request, status="needs_info")
        event = await emit_approval_decided(
            self.session,
            request=request,
            level=level,
            assignment=assignment,
            decision=decision,
            actor_id=command.actor_id,
            decision_type=command.decision_type,
            old_revision_ref=old_revision_ref,
            new_revision_ref=approval_revision_ref(request),
            metadata={
                "clarification_request_id": clarification_request_id,
            },
        )
        return self._result(
            request=request,
            level=level,
            assignment=assignment,
            actor_id=command.actor_id,
            decision_id=decision.id,
            event_id=event.id,
            decision_type=command.decision_type,
            reason=command.reason,
            clarification_request_id=clarification_request_id,
            include_resume_payload=False,
        )

    async def _edit(
        self,
        command: ApprovalDecisionCommand,
        request: ApprovalRequest,
        level: ApprovalLevel,
        assignment: ApprovalAssignment,
    ) -> ApprovalDecisionResult:
        old_revision_ref = approval_revision_ref(request)
        snapshot_row = await self.repository.get_snapshot_by_ref_or_hash(
            tenant_id=request.tenant_id,
            safety_snapshot_ref=request.safety_snapshot_ref,
            safety_snapshot_hash=request.safety_snapshot_hash,
        )
        if snapshot_row is None:
            raise ApprovalTransitionError("approval_not_executable")

        proposed_action, evidence_refs = self._replacement_action_and_evidence(
            request,
            {"edited_action": command.edited_action},
        )
        snapshot = await persist_action_safety_snapshot(
            self.session,
            tenant_id=request.tenant_id,
            run_id=request.run_id,
            proposed_action=proposed_action,
            action_payload_hash=None,
            policy_config_version=snapshot_row.policy_config_version,
            risk_config_version=snapshot_row.risk_config_version,
            retrieval_config_version=snapshot_row.retrieval_config_version,
            evidence_refs=evidence_refs,
            created_at=self._fixed_millisecond_now(),
            created_by=command.actor_id,
            repository=self.repository,
        )
        decision = await self.repository.insert_decision(
            request=request,
            level=level,
            assignment=assignment,
            actor_id=command.actor_id,
            decision_type=command.decision_type,
            reason=command.reason,
            edited_action=command.edited_action,
        )
        await self.repository.increment_assignment_version(assignment, status="skipped")
        await self.repository.increment_level_version(level, status="skipped")
        await self.repository.increment_request_version(request, status="superseded")
        new_request, _new_level, _new_assignment, _event = await self.repository.create_request_with_single_level(
            tenant_id=request.tenant_id,
            run_id=request.run_id,
            thread_id=request.thread_id,
            requested_by=request.requested_by,
            proposed_action=proposed_action,
            approval_policy_id=request.approval_policy_id or "manual-review",
            policy_version=request.policy_version or "policy.v1",
            risk_level=request.risk_level,
            risk_rule_ref=request.risk_rule_ref,
            action_payload_hash=snapshot.action_payload_hash,
            safety_snapshot_ref=snapshot.safety_snapshot_ref,
            safety_snapshot_hash=snapshot.safety_snapshot_hash,
            expires_at=request.expires_at,
            required_role=level.required_role,
            assigned_role=assignment.assigned_role,
            level_mode=level.mode,
            sla_due_at=level.sla_due_at or request.expires_at,
            risk_reason=request.risk_reason,
        )
        request.superseded_by_request_id = new_request.id
        await self.session.flush()
        event = await emit_approval_decided(
            self.session,
            request=request,
            level=level,
            assignment=assignment,
            decision=decision,
            actor_id=command.actor_id,
            decision_type=command.decision_type,
            old_revision_ref=old_revision_ref,
            new_revision_ref=approval_revision_ref(new_request),
            metadata={
                "resume_route": "assess_risk_and_approval",
                "superseded_by_request_id": str(new_request.id),
            },
            resource_refs={
                "old_action_payload_hash": request.action_payload_hash,
                "old_safety_snapshot_ref": request.safety_snapshot_ref,
                "old_safety_snapshot_hash": request.safety_snapshot_hash,
                "new_action_payload_hash": new_request.action_payload_hash,
                "new_safety_snapshot_ref": new_request.safety_snapshot_ref,
                "new_safety_snapshot_hash": new_request.safety_snapshot_hash,
            },
        )
        await emit_approval_requested(
            self.session,
            request=new_request,
            level=_new_level,
            assignment=_new_assignment,
            actor_id=request.requested_by,
            existing_event=_event,
            metadata={"superseded_from_request_id": str(request.id)},
        )
        return self._result(
            request=request,
            level=level,
            assignment=assignment,
            actor_id=command.actor_id,
            decision_id=decision.id,
            event_id=event.id,
            decision_type=command.decision_type,
            reason=command.reason,
            superseded_by_request_id=new_request.id,
            new_action_payload_hash=new_request.action_payload_hash,
            edited_action=command.edited_action,
            resume_route="assess_risk_and_approval",
        )

    async def _terminal_decision(
        self,
        command: ApprovalDecisionCommand,
        request: ApprovalRequest,
        level: ApprovalLevel,
        assignment: ApprovalAssignment,
        *,
        status: str,
    ) -> ApprovalDecisionResult:
        decision = await self.repository.insert_decision(
            request=request,
            level=level,
            assignment=assignment,
            actor_id=command.actor_id,
            decision_type=command.decision_type,
            reason=command.reason,
            response_text=command.response_text,
            edited_action=command.edited_action,
        )
        assignment_status = "rejected" if status == "rejected" else "cancelled"
        await self.repository.increment_assignment_version(assignment, status=assignment_status)
        await self.repository.increment_level_version(level, status=assignment_status)
        await self.repository.increment_request_version(request, status=status)
        event = await emit_approval_decided(
            self.session,
            request=request,
            level=level,
            assignment=assignment,
            decision=decision,
            actor_id=command.actor_id,
            decision_type=command.decision_type,
        )
        return self._result(
            request=request,
            level=level,
            assignment=assignment,
            actor_id=command.actor_id,
            decision_id=decision.id,
            event_id=event.id,
            decision_type=command.decision_type,
            reason=command.reason,
        )

    async def _revalidate_same_revision(
        self,
        command: ApprovalInfoCommand,
        request: ApprovalRequest,
        level: ApprovalLevel,
        assignment: ApprovalAssignment,
    ) -> ApprovalInfoResult:
        await self.repository.increment_assignment_version(assignment)
        await self.repository.increment_level_version(level)
        await self.repository.increment_request_version(request, status="pending")
        await self.repository.insert_approval_event(
            request=request,
            event_type="approval_info_attached",
            actor_id=command.actor_id,
            level=level,
            assignment=assignment,
            metadata={
                "clarification_request_id": command.clarification_request_id,
                "changed_revision_material": False,
            },
            resource_refs={
                "action_payload_hash": request.action_payload_hash,
                "safety_snapshot_ref": request.safety_snapshot_ref,
                "safety_snapshot_hash": request.safety_snapshot_hash,
            },
        )
        return self._info_result(
            request=request,
            level=level,
            assignment=assignment,
            clarification_request_id=command.clarification_request_id,
        )

    async def _supersede_from_info(
        self,
        command: ApprovalInfoCommand,
        request: ApprovalRequest,
        level: ApprovalLevel,
        assignment: ApprovalAssignment,
    ) -> ApprovalInfoResult:
        snapshot_row = await self.repository.get_snapshot_by_ref_or_hash(
            tenant_id=request.tenant_id,
            safety_snapshot_ref=request.safety_snapshot_ref,
            safety_snapshot_hash=request.safety_snapshot_hash,
        )
        if snapshot_row is None:
            raise ApprovalTransitionError("approval_not_executable")

        proposed_action, evidence_refs = self._replacement_action_and_evidence(request, command.info_payload)
        snapshot = await persist_action_safety_snapshot(
            self.session,
            tenant_id=request.tenant_id,
            run_id=request.run_id,
            proposed_action=proposed_action,
            action_payload_hash=command.info_payload.get("action_payload_hash"),
            policy_config_version=str(
                command.info_payload.get("policy_config_version") or snapshot_row.policy_config_version
            ),
            risk_config_version=str(command.info_payload.get("risk_config_version") or snapshot_row.risk_config_version),
            retrieval_config_version=str(
                command.info_payload.get("retrieval_config_version") or snapshot_row.retrieval_config_version
            ),
            evidence_refs=evidence_refs,
            created_at=self._fixed_millisecond_now(),
            created_by=command.actor_id,
            repository=self.repository,
        )

        await self.repository.increment_assignment_version(assignment, status="skipped")
        await self.repository.increment_level_version(level, status="skipped")
        await self.repository.increment_request_version(request, status="superseded")
        new_request, new_level, new_assignment, _event = await self.repository.create_request_with_single_level(
            tenant_id=request.tenant_id,
            run_id=request.run_id,
            thread_id=request.thread_id,
            requested_by=request.requested_by,
            proposed_action=proposed_action,
            approval_policy_id=request.approval_policy_id or "manual-review",
            policy_version=request.policy_version or "policy.v1",
            risk_level=request.risk_level,
            risk_rule_ref=request.risk_rule_ref,
            action_payload_hash=snapshot.action_payload_hash,
            safety_snapshot_ref=snapshot.safety_snapshot_ref,
            safety_snapshot_hash=snapshot.safety_snapshot_hash,
            expires_at=request.expires_at,
            required_role=level.required_role,
            assigned_role=assignment.assigned_role,
            level_mode=level.mode,
            sla_due_at=level.sla_due_at or request.expires_at,
            risk_reason=request.risk_reason,
        )
        request.superseded_by_request_id = new_request.id
        await self.session.flush()
        await emit_approval_requested(
            self.session,
            request=new_request,
            level=new_level,
            assignment=new_assignment,
            actor_id=request.requested_by,
            existing_event=_event,
            metadata={"superseded_from_request_id": str(request.id)},
        )
        await self.repository.insert_approval_event(
            request=request,
            event_type="approval_info_attached",
            actor_id=command.actor_id,
            level=level,
            assignment=assignment,
            metadata={
                "clarification_request_id": command.clarification_request_id,
                "changed_revision_material": True,
                "superseded_by_request_id": str(new_request.id),
            },
            resource_refs={
                "old_action_payload_hash": request.action_payload_hash,
                "old_safety_snapshot_hash": request.safety_snapshot_hash,
                "new_action_payload_hash": new_request.action_payload_hash,
                "new_safety_snapshot_ref": new_request.safety_snapshot_ref,
                "new_safety_snapshot_hash": new_request.safety_snapshot_hash,
            },
        )
        return self._info_result(
            request=new_request,
            level=new_level,
            assignment=new_assignment,
            clarification_request_id=command.clarification_request_id,
            superseded_request_id=request.id,
            superseded_by_request_id=new_request.id,
            new_action_payload_hash=new_request.action_payload_hash,
        )

    def _result(
        self,
        *,
        request: ApprovalRequest,
        level: ApprovalLevel,
        assignment: ApprovalAssignment,
        actor_id: UUID,
        decision_id: UUID,
        event_id: UUID,
        decision_type: str,
        reason: str | None = None,
        clarification_request_id: str | None = None,
        superseded_by_request_id: UUID | None = None,
        new_action_payload_hash: str | None = None,
        edited_action: dict[str, Any] | None = None,
        resume_route: str | None = None,
        include_resume_payload: bool = True,
    ) -> ApprovalDecisionResult:
        decided_at = datetime.now(UTC)
        request.decision = decision_type
        request.decided_by = actor_id
        request.decided_at = decided_at
        trusted = TrustedApprovalResultV1(
            approval_id=request.id,
            tenant_id=request.tenant_id,
            run_id=request.run_id,
            status=request.status,
            decision_type=decision_type,
            revision=request.revision,
            request_version=request.version,
            level_version=level.version,
            assignment_version=assignment.version,
            action_payload_hash=request.action_payload_hash,
            safety_snapshot_ref=request.safety_snapshot_ref,
            safety_snapshot_hash=request.safety_snapshot_hash,
            decided_by=actor_id,
            decided_at=decided_at,
            reason=reason,
            clarification_request_id=clarification_request_id,
            superseded_by_request_id=superseded_by_request_id,
            new_action_payload_hash=new_action_payload_hash,
            edited_action=edited_action,
            resume_route=resume_route,
        ).model_dump(mode="json")
        if trusted["schema_version"] != "approval_result.v1":
            raise ApprovalTransitionError("approval_invalid_result")
        return ApprovalDecisionResult(
            approval_id=request.id,
            tenant_id=request.tenant_id,
            run_id=request.run_id,
            status=request.status,
            decision_type=decision_type,
            revision=request.revision,
            request_version=request.version,
            level_version=level.version,
            assignment_version=assignment.version,
            action_payload_hash=request.action_payload_hash,
            safety_snapshot_ref=request.safety_snapshot_ref,
            safety_snapshot_hash=request.safety_snapshot_hash,
            decided_by=actor_id,
            decided_at=decided_at,
            decision_id=decision_id,
            event_id=event_id,
            reason=reason,
            clarification_request_id=clarification_request_id,
            superseded_by_request_id=superseded_by_request_id,
            new_action_payload_hash=new_action_payload_hash,
            edited_action=edited_action,
            resume_payload=trusted if include_resume_payload else None,
            graph_thread_id=self._graph_thread_id(request),
        )

    def _info_result(
        self,
        *,
        request: ApprovalRequest,
        level: ApprovalLevel,
        assignment: ApprovalAssignment,
        clarification_request_id: str,
        superseded_request_id: UUID | None = None,
        superseded_by_request_id: UUID | None = None,
        new_action_payload_hash: str | None = None,
    ) -> ApprovalInfoResult:
        return ApprovalInfoResult(
            approval_id=request.id,
            tenant_id=request.tenant_id,
            run_id=request.run_id,
            status=request.status,
            revision=request.revision,
            request_version=request.version,
            level_id=level.id,
            level_version=level.version,
            assignment_id=assignment.id,
            assignment_version=assignment.version,
            action_payload_hash=request.action_payload_hash,
            safety_snapshot_ref=request.safety_snapshot_ref,
            safety_snapshot_hash=request.safety_snapshot_hash,
            clarification_request_id=clarification_request_id,
            superseded_request_id=superseded_request_id,
            superseded_by_request_id=superseded_by_request_id,
            new_action_payload_hash=new_action_payload_hash,
            resume_payload=None,
            graph_thread_id=self._graph_thread_id(request),
        )

    @staticmethod
    def _assert_create_context(command: ApprovalRequestCreateCommand) -> None:
        required_values = [
            command.risk_level,
            command.policy_config_version,
            command.risk_config_version,
            command.retrieval_config_version,
            command.proposed_action,
            command.evidence_refs,
        ]
        if any(not value for value in required_values):
            raise ApprovalTransitionError("approval_not_executable")

    @staticmethod
    def _assert_executable_request(request: ApprovalRequest) -> None:
        if request.legacy_non_executable or request.schema_version != "approval_request.v2":
            raise ApprovalTransitionError("approval_not_executable")
        required = [
            request.revision,
            request.version,
            request.action_payload_hash,
            request.safety_snapshot_ref,
            request.safety_snapshot_hash,
            request.risk_level,
        ]
        if any(not value for value in required):
            raise ApprovalTransitionError("approval_not_executable")

    @staticmethod
    def _assert_request_binding(request: ApprovalRequest, command: ApprovalDecisionCommand) -> None:
        if request.run_id != command.run_id or request.thread_id != command.thread_id:
            raise ApprovalTransitionError("approval_conflict")

    async def _assert_snapshot_binding(self, request: ApprovalRequest) -> None:
        snapshot = await self.repository.get_snapshot_by_ref_or_hash(
            tenant_id=request.tenant_id,
            safety_snapshot_ref=request.safety_snapshot_ref,
            safety_snapshot_hash=request.safety_snapshot_hash,
        )
        if snapshot is None or snapshot.action_payload_hash != request.action_payload_hash:
            raise ApprovalTransitionError("approval_not_executable")

    @staticmethod
    def _assert_hash_binding(request: ApprovalRequest, command: ApprovalDecisionCommand) -> None:
        if (
            request.action_payload_hash != command.action_payload_hash
            or request.safety_snapshot_hash != command.safety_snapshot_hash
        ):
            raise ApprovalTransitionError("approval_hash_mismatch")

    @staticmethod
    def _assert_pending_request(request: ApprovalRequest) -> None:
        if request.status != "pending":
            raise ApprovalTransitionError("approval_conflict")
        if request.expires_at <= datetime.now(UTC):
            raise ApprovalTransitionError("approval_conflict")

    @staticmethod
    def _assert_needs_info_request(request: ApprovalRequest, command: ApprovalInfoCommand) -> None:
        if request.status != "needs_info":
            raise ApprovalTransitionError("approval_conflict")
        if request.thread_id != command.thread_id:
            raise ApprovalTransitionError("approval_conflict")
        if request.clarification_request_id != command.clarification_request_id:
            raise ApprovalTransitionError("approval_conflict")
        if request.expires_at <= datetime.now(UTC):
            raise ApprovalTransitionError("approval_conflict")

    @staticmethod
    def _assert_assignment_can_transition(assignment: ApprovalAssignment) -> None:
        if assignment.status != "pending":
            raise ApprovalTransitionError("approval_conflict")

    @staticmethod
    def _info_changes_revision_material(info_payload: dict[str, Any]) -> bool:
        revision_material_keys = {
            "proposed_action",
            "edited_action",
            "evidence_refs",
            "policy_config_version",
            "risk_config_version",
            "retrieval_config_version",
            "action_payload_hash",
            "safety_snapshot_hash",
        }
        return any(key in info_payload for key in revision_material_keys)

    def _replacement_action_and_evidence(
        self,
        request: ApprovalRequest,
        info_payload: dict[str, Any],
    ) -> tuple[dict[str, Any], list[EvidenceRefV1]]:
        proposed_action = dict(info_payload.get("proposed_action") or info_payload.get("edited_action") or request.proposed_action)
        evidence_payload = info_payload.get("evidence_refs")
        if evidence_payload is not None:
            evidence_refs = self._parse_evidence_refs(evidence_payload)
            proposed_action["evidence_refs"] = canonical_evidence_projection(evidence_refs)
            return proposed_action, evidence_refs
        evidence_refs = self._parse_evidence_refs(proposed_action.get("evidence_refs") or [])
        proposed_action["evidence_refs"] = canonical_evidence_projection(evidence_refs)
        return proposed_action, evidence_refs

    @staticmethod
    def _parse_evidence_refs(raw_refs: Any) -> list[EvidenceRefV1]:
        if not isinstance(raw_refs, list) or not raw_refs:
            raise ApprovalTransitionError("approval_not_executable")
        refs: list[EvidenceRefV1] = []
        for raw in raw_refs:
            item = raw.model_dump(mode="json") if hasattr(raw, "model_dump") else raw
            refs.append(EvidenceRefV1.model_validate(item))
        return refs

    @staticmethod
    def _graph_thread_id(request: ApprovalRequest) -> str:
        return f"{request.tenant_id}:{request.requested_by}:{request.thread_id}"

    @staticmethod
    def _fixed_millisecond_now() -> datetime:
        now = datetime.now(UTC)
        return now.replace(microsecond=(now.microsecond // 1000) * 1000)
