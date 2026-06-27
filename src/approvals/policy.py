"""Approval policy helpers for assignment, role, SLA, and self-approval rules."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID

APPROVAL_ROLES = {"admin"}


class ApprovalPolicyError(ValueError):
    """Raised when an actor violates approval policy."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class ApprovalAssignmentPlan:
    required_role: str
    assigned_role: str
    mode: str
    sla_due_at: datetime


class ApprovalPolicy:
    """Policy owner for Phase 13 single-level approval runtime."""

    def __init__(
        self,
        *,
        allowed_roles: set[str] | None = None,
        default_required_role: str = "manager",
        default_mode: str = "any_one",
        default_sla: timedelta = timedelta(hours=24),
    ) -> None:
        self.allowed_roles = allowed_roles or APPROVAL_ROLES
        self.default_required_role = default_required_role
        self.default_mode = default_mode
        self.default_sla = default_sla

    def assert_actor_can_review(self, *, actor_role: str, assigned_role: str | None = None) -> None:
        if actor_role not in self.allowed_roles:
            raise ApprovalPolicyError("approval_forbidden", "actor role cannot review approvals")
        if assigned_role and actor_role != assigned_role and actor_role != "admin":
            raise ApprovalPolicyError("approval_forbidden", "actor role does not match assignment")

    def assert_not_self_approval(self, *, requested_by: UUID, actor_id: UUID) -> None:
        if requested_by == actor_id:
            raise ApprovalPolicyError("approval_forbidden", "self-approval is not allowed")

    def default_single_level_assignment(
        self,
        *,
        now: datetime,
        required_role: str | None = None,
        mode: str | None = None,
    ) -> ApprovalAssignmentPlan:
        role = required_role or self.default_required_role
        return ApprovalAssignmentPlan(
            required_role=role,
            assigned_role=role,
            mode=mode or self.default_mode,
            sla_due_at=self.sla_due_at(now),
        )

    def sla_due_at(self, now: datetime) -> datetime:
        return now + self.default_sla
