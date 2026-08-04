from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from scripts.seed_demo import deterministic_id, reset_demo_data
from src.db.models import (
    AgentRun,
    ApprovalAssignment,
    ApprovalDecision,
    ApprovalLevel,
    ApprovalRequest,
    Tenant,
    User,
)


class _ScalarResult:
    def __init__(self, values):
        self._values = values

    def all(self):
        return self._values


class _ExecuteResult:
    def __init__(self, values):
        self._values = values

    def scalars(self):
        return _ScalarResult(self._values)


class _FakeSession:
    def __init__(self, select_results):
        self.select_results = list(select_results)
        self.statements = []
        self.committed = False

    async def execute(self, statement):
        self.statements.append(statement)
        if getattr(statement, "__visit_name__", "") == "select":
            return _ExecuteResult(self.select_results.pop(0))
        return _ExecuteResult([])

    async def commit(self):
        self.committed = True


@pytest.mark.asyncio
async def test_reset_demo_data_deletes_agent_and_approval_rows_before_users():
    session = _FakeSession(
        select_results=[
            [uuid4()],  # user ids
            [uuid4()],  # agent run ids
            [uuid4()],  # approval request ids
            [uuid4()],  # approval level ids
        ]
    )

    await reset_demo_data(session)

    delete_tables = [
        statement.table.name for statement in session.statements if getattr(statement, "__visit_name__", "") == "delete"
    ]
    mutation_kinds = [
        (getattr(statement, "__visit_name__", ""), statement.table.name)
        for statement in session.statements
        if getattr(statement, "__visit_name__", "") in {"update", "delete"}
    ]

    assert mutation_kinds.index(("update", "approval_requests")) < mutation_kinds.index(
        ("delete", "approval_decisions")
    )
    assert delete_tables.index("approval_steps") < delete_tables.index("approval_requests")
    assert delete_tables.index("approval_assignments") < delete_tables.index("approval_levels")
    assert delete_tables.index("approval_levels") < delete_tables.index("approval_requests")
    assert delete_tables.index("action_drafts") < delete_tables.index("approval_requests")
    assert delete_tables.index("approval_requests") < delete_tables.index("users")
    assert delete_tables.index("agent_steps") < delete_tables.index("agent_runs")
    assert delete_tables.index("agent_runs") < delete_tables.index("users")
    assert session.committed is True


@pytest.mark.asyncio
async def test_reset_demo_data_clears_resume_decision_reference_before_deleting_decision(
    session: AsyncSession,
) -> None:
    now = datetime.now(UTC)
    tenant = Tenant(id=deterministic_id("tenant", "demo"), name="Demo Tenant", status="active")
    user = User(
        id=uuid4(),
        tenant_id=tenant.id,
        username="reset-demo-admin",
        password_hash="test-only",
        role="admin",
        is_active=True,
    )
    run = AgentRun(
        id=uuid4(),
        thread_id="reset-demo-resume-thread",
        tenant_id=tenant.id,
        user_id=user.id,
        input_query="reset demo data",
        final_status="completed",
        scope_classification="unknown_legacy",
        started_at=now,
    )
    request = ApprovalRequest(
        id=uuid4(),
        run_id=run.id,
        tenant_id=tenant.id,
        status="approved",
        revision=1,
        version=1,
        requested_by=user.id,
        proposed_action={"action_type": "issue_coupon"},
        risk_level="high",
        expires_at=now + timedelta(hours=1),
        thread_id=run.thread_id,
    )
    level = ApprovalLevel(
        id=uuid4(),
        approval_request_id=request.id,
        level_number=1,
        status="approved",
        required_role="admin",
        mode="any_one",
    )
    assignment = ApprovalAssignment(
        id=uuid4(),
        approval_level_id=level.id,
        assigned_role="admin",
        assigned_to_user_id=user.id,
        status="approved",
    )
    decision = ApprovalDecision(
        id=uuid4(),
        approval_request_id=request.id,
        approval_level_id=level.id,
        approval_assignment_id=assignment.id,
        tenant_id=tenant.id,
        run_id=run.id,
        thread_id=run.thread_id,
        request_revision=1,
        request_version=1,
        level_version=1,
        level_mode="any_one",
        assignment_version=1,
        decision_type="approve",
        actor_id=user.id,
    )
    session.add_all([tenant, user, run, request, level, assignment, decision])
    await session.flush()
    request.resume_attempt_id = uuid4()
    request.resume_attempt_decision_id = decision.id
    request.resume_attempt_status = "completed"
    request.resume_attempt_started_at = now
    request.resume_attempt_updated_at = now
    await session.commit()

    await reset_demo_data(session)

    for model, row_id in (
        (ApprovalRequest, request.id),
        (ApprovalLevel, level.id),
        (ApprovalAssignment, assignment.id),
        (ApprovalDecision, decision.id),
    ):
        remaining = await session.execute(select(model.id).where(model.id == row_id))
        assert remaining.scalar_one_or_none() is None
