from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.actions.schemas import DraftOutcomeV1
from src.agent.graph_vocabulary import project_trace_step_for_contract
from src.db.models import ActionDraft, AgentRun, AgentStep, ApprovalRequest, ApprovalStep

_DRAFT_OUTCOME_KEYS = frozenset(
    {
        "schema_version",
        "status",
        "external_side_effect",
        "tenant_id",
        "run_id",
        "draft_id",
        "created_at",
    }
)


class TraceRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_run(self, run_id: UUID, tenant_id: UUID) -> AgentRun | None:
        stmt = select(AgentRun).where(AgentRun.id == run_id, AgentRun.tenant_id == tenant_id)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_steps(self, run_id: UUID) -> list[AgentStep]:
        stmt = select(AgentStep).where(AgentStep.run_id == run_id).order_by(AgentStep.step_index)
        return list((await self.session.execute(stmt)).scalars().all())

    async def get_approvals(self, run_id: UUID) -> list[ApprovalRequest]:
        stmt = select(ApprovalRequest).where(ApprovalRequest.run_id == run_id).order_by(ApprovalRequest.created_at)
        return list((await self.session.execute(stmt)).scalars().all())

    async def get_approval_steps(self, approval_ids: list[UUID]) -> list[ApprovalStep]:
        if not approval_ids:
            return []
        stmt = (
            select(ApprovalStep)
            .where(ApprovalStep.approval_request_id.in_(approval_ids))
            .order_by(ApprovalStep.created_at)
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def get_action_drafts(self, run_id: UUID) -> list[ActionDraft]:
        stmt = select(ActionDraft).where(ActionDraft.run_id == run_id).order_by(ActionDraft.created_at)
        return list((await self.session.execute(stmt)).scalars().all())

    def build_timeline(
        self,
        steps: list[AgentStep],
        approvals: list[ApprovalRequest],
        approval_steps: list[ApprovalStep],
        drafts: list[ActionDraft],
    ) -> list[dict[str, Any]]:
        timeline: list[dict[str, Any]] = []

        for step in steps:
            projected = project_trace_step_for_contract({"node": step.node_name})
            timeline.append(
                {
                    "type": "agent_step",
                    "time": step.started_at.isoformat(),
                    "title": f"Node: {step.node_name}",
                    "status": step.status,
                    "detail": {
                        "node_name": step.node_name,
                        "target_node": projected["target_node"],
                        "tool_name": step.tool_name,
                        "latency_ms": step.latency_ms,
                        "provider_latency_ms": step.provider_latency_ms,
                    },
                }
            )

        for approval in approvals:
            timeline.append(
                {
                    "type": "approval_request",
                    "time": approval.created_at.isoformat(),
                    "title": f"Approval requested: {approval.risk_rule_ref or 'unknown rule'}",
                    "status": approval.status,
                    "detail": {
                        "approval_id": str(approval.id),
                        "risk_level": approval.risk_level,
                        "proposed_action": _safe_proposed_action(approval.proposed_action),
                    },
                }
            )

        for approval_step in approval_steps:
            timeline.append(
                {
                    "type": "approval_decision",
                    "time": approval_step.created_at.isoformat(),
                    "title": f"Approval {approval_step.event_type}",
                    "status": approval_step.event_type,
                    "detail": {
                        "actor_id": str(approval_step.actor_id) if approval_step.actor_id else None,
                        "metadata": approval_step.metadata_json,
                    },
                }
            )

        for draft in drafts:
            timeline.append(
                {
                    "type": "action_draft",
                    "time": draft.created_at.isoformat(),
                    "title": f"Action: {draft.action_type}",
                    "status": draft.status,
                    "detail": {
                        "draft_id": str(draft.id),
                        "draft_outcome": _safe_draft_outcome(draft),
                    },
                }
            )

        timeline.sort(key=lambda item: item["time"])
        return timeline


def _safe_proposed_action(action: dict[str, Any] | None) -> dict[str, Any]:
    action = action or {}
    return {
        "action_type": action.get("action_type"),
        "amount": action.get("amount"),
        "currency": action.get("currency"),
    }


def _safe_draft_outcome(draft: ActionDraft) -> dict[str, Any]:
    outcome = draft.draft_outcome if isinstance(draft.draft_outcome, dict) else {}
    projected = {key: outcome[key] for key in _DRAFT_OUTCOME_KEYS if key in outcome}
    try:
        return DraftOutcomeV1.model_validate(projected).model_dump(mode="json")
    except ValidationError:
        return {"status": "invalid_draft_outcome", "external_side_effect": False}
