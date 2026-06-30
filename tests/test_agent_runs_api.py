from __future__ import annotations

import asyncio
import contextlib
import inspect
import json
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.main import app
from src.agent.merchant_context import project_target_merchant_context
from src.agent.run_scope import BUSINESS_MERCHANT
from src.agent.trace import write_agent_run
from src.api.routers.agent_runs import (
    ADMIN_RUN_VISIBILITY_ROLES,
    APPROVAL_NOT_EXECUTABLE,
    _dedupe_evidence_refs,
    _ensure_can_execute_run,
    _ensure_can_view_run,
    _event_generator,
    _extract_step_payload,
    _sse_event,
)
from src.api.services.agent_run_memory import finalize_completed_agent_run_memory
from src.approvals.schemas import PROPOSED_ACTION_SCHEMA_VERSION
from src.approvals.snapshot_service import compute_action_payload_hash, persist_action_safety_snapshot
from src.auth.jwt import ROLE_SCOPES, create_access_token, hash_password
from src.db.models import (
    AgentRun,
    AgentStep,
    AgentTraceEvent,
    ApprovalRequest,
    ConversationMessage,
    ConversationSummary,
    MemoryWriteEvent,
    SessionMemory,
    ToolResultRecord,
    User,
)
from src.knowledge.schemas import EvidenceRefV1
from src.platform.context_projections import project_to_legacy_agent_state_identity
from src.platform.trusted_context import TrustedContext
from src.tools.contracts import BusinessFactRefV1, ToolResultV2


class NeverCalledGraph:
    def __init__(self) -> None:
        self.calls: list[tuple[object, dict]] = []

    async def astream(self, input_state, config, stream_mode):
        self.calls.append((input_state, config))
        raise AssertionError("graph.astream must not be called")
        yield


class CaptureConfigGraph:
    def __init__(self) -> None:
        self.calls: list[tuple[object, dict]] = []

    async def astream(self, input_state, config, stream_mode):
        self.calls.append((input_state, config))
        yield ("final_response", {"final_response": "done", "trace_steps": []})


class ThreeTurnMemoryGraph:
    def __init__(self) -> None:
        self.calls: list[tuple[object, dict]] = []
        self.snapshots: list[dict] = []

    async def astream(self, input_state, config, stream_mode):
        from src.memory.repository import SessionMemoryRepository
        from src.memory.service import MemoryService

        self.calls.append((input_state, config))
        configurable = config["configurable"]
        session = configurable["session"]
        conversation_service = configurable["conversation_service"]
        run_id = UUID(input_state["current_run_id"])
        query = input_state["user_query"]
        prompt_context = await conversation_service.load_prompt_context(
            tenant_id=input_state["tenant_id"],
            user_id=input_state["user_id"],
            thread_id=input_state["thread_id"],
            run_id=run_id,
        )
        session_memory = await MemoryService(SessionMemoryRepository(session)).load_session_memory(
            input_state["tenant_id"],
            input_state["user_id"],
            input_state["thread_id"],
            current_intent="refund_troubleshooting",
        )
        extracted_slots, active_slots, active_slot_metadata = self._resolve_slots(query, session_memory)
        await self._append_tool_result(
            conversation_service=conversation_service,
            input_state=input_state,
            config=config,
            run_id=run_id,
            order_id=active_slots["order_id"],
        )
        final_state = {
            "current_run_id": str(run_id),
            "current_intent": "refund_troubleshooting",
            "primary_intent": "refund_troubleshooting",
            "requested_operation": "read_status",
            "extracted_slots": extracted_slots,
            "active_slots": active_slots,
            "active_slot_metadata": active_slot_metadata,
            "session_memory": session_memory.model_dump(mode="json"),
            "last_business_context_refs": {
                "business_fact_refs": [{"resource_type": "order", "resource_id": active_slots["order_id"]}]
            },
            "retrieved_evidence": {
                "evidence_refs": [
                    _evidence_ref(input_state["tenant_id"], active_slots["order_id"]).model_dump(
                        mode="json", exclude_none=True
                    )
                ]
            },
            "final_response": f"已基于当前工具和政策证据处理 {active_slots['order_id']}。",
            "trace_steps": [
                _trace("extract_slots"),
                _trace("investigate"),
                _trace("final_response"),
            ],
        }
        self.snapshots.append(
            {
                "query": query,
                "prompt_summary": getattr(prompt_context.latest_thread_summary, "summary_text", "") or "",
                "recent_messages": [(message.role, message.content) for message in prompt_context.recent_messages],
                "tool_prompt_summaries": [
                    result.prompt_summary or "" for result in prompt_context.tool_prompt_summaries
                ],
                "session_memory": session_memory.model_dump(mode="json"),
                "active_slots": dict(active_slots),
                "active_slot_metadata": dict(active_slot_metadata),
                "retrieved_evidence": final_state["retrieved_evidence"],
                "last_business_context_refs": final_state["last_business_context_refs"],
            }
        )
        yield ("extract_slots", {"active_slots": active_slots, "active_slot_metadata": active_slot_metadata})
        yield ("investigate", {"retrieved_evidence": final_state["retrieved_evidence"]})
        yield ("final_response", final_state)

    def _resolve_slots(self, query: str, session_memory) -> tuple[dict, dict, dict]:
        if "ORD-TEST-999" in query:
            extracted = {"order_id": "ORD-TEST-999", "refund_case_id": None, "issue_type": "refund_status"}
            return extracted, {"order_id": "ORD-TEST-999", "issue_type": "refund_status"}, {
                "order_id": {
                    "source": "explicit_user",
                    "previous_trusted_session_value": session_memory.active_slots.get("order_id"),
                },
                "issue_type": {"source": "explicit_user"},
            }
        if "ORD-TEST-001" in query:
            extracted = {
                "order_id": "ORD-TEST-001",
                "refund_case_id": "RF-TEST-001",
                "issue_type": "refund_status",
            }
            return extracted, dict(extracted), {
                "order_id": {"source": "explicit_user"},
                "refund_case_id": {"source": "explicit_user"},
                "issue_type": {"source": "explicit_user"},
            }
        inherited = dict(session_memory.active_slots)
        if "issue_type" not in inherited:
            inherited["issue_type"] = "refund_status"
        metadata = dict(session_memory.slot_metadata)
        metadata["issue_type"] = {"source": "explicit_user"}
        return {"order_id": None, "refund_case_id": None, "issue_type": "refund_status"}, inherited, metadata

    async def _append_tool_result(self, *, conversation_service, input_state, config, run_id: UUID, order_id: str) -> None:
        operation_id = uuid4()
        tool_call_id = f"tool-call-{run_id}"
        tool_call = await conversation_service.append_tool_call(
            tenant_id=input_state["tenant_id"],
            user_id=input_state["user_id"],
            thread_id=input_state["thread_id"],
            run_id=run_id,
            trace_id=config["configurable"].get("trace_id"),
            tool_call_id=tool_call_id,
            tool_name="get_order",
            caller_node="investigate",
            operation_id=operation_id,
            attempt=1,
            arguments={"order_no": order_id},
            argument_summary_json={"order_no": order_id},
            redaction_policy_version="conversation_redaction.v1",
            conversation_message_id=config["configurable"]["conversation_message_id"],
        )
        business_ref = BusinessFactRefV1(
            tenant_id=input_state["tenant_id"],
            source_system="business_tool_service",
            resource_type="order",
            resource_id=order_id,
            resource_version=None,
            data_freshness_at=datetime.now(UTC),
            retrieved_at=datetime.now(UTC),
        )
        await conversation_service.append_tool_result(
            tenant_id=input_state["tenant_id"],
            user_id=input_state["user_id"],
            thread_id=input_state["thread_id"],
            run_id=run_id,
            trace_id=config["configurable"].get("trace_id"),
            operation_id=operation_id,
            tool_call_id=tool_call_id,
            tool_call_record_id=tool_call.id,
            conversation_message_id=config["configurable"]["conversation_message_id"],
            tool_result_id=f"tool-result-{run_id}",
            tool_name="get_order",
            result=ToolResultV2(
                status="success",
                data={"order_id": order_id, "refund_status": "reviewing"},
                summary=f"Prompt-safe get_order summary for {order_id}.",
                source_system="business_tool_service",
                data_freshness_at=datetime.now(UTC),
                policy_evidence_refs=[_evidence_ref(input_state["tenant_id"], order_id)],
                business_fact_refs=[business_ref],
                error=None,
                retryable=False,
                retry_after_ms=None,
                latency_ms=8,
                audit_ref=f"audit/tool-result/{order_id}",
            ),
            raw_result_ref=f"raw-result://orders/{order_id}",
            raw_result_hash=f"sha256:{run_id.hex}",
        )


class ErrorGraph:
    async def astream(self, input_state, config, stream_mode):
        raise RuntimeError("graph failed")
        yield


class CaptureInvokeConfigGraph:
    def __init__(self) -> None:
        self.calls: list[tuple[object, dict]] = []

    async def ainvoke(self, input_state, config):
        self.calls.append((input_state, config))
        return {"final_response": "done", "trace_steps": []}


class SpoofRunIdInvokeGraph:
    def __init__(self, spoof_run_id: str) -> None:
        self.spoof_run_id = spoof_run_id
        self.calls: list[tuple[object, dict]] = []

    async def ainvoke(self, input_state, config):
        self.calls.append((input_state, config))
        return {
            "current_run_id": self.spoof_run_id,
            "final_response": "done",
            "trace_steps": [],
        }


class FakeStateSnapshot:
    def __init__(self, values: dict) -> None:
        self.values = values


class FakeGraphInterrupt(Exception):
    pass


class SpoofInterruptInvokeGraph:
    def __init__(
        self,
        *,
        interrupt_run_id: str | None = None,
        checkpoint_run_id: str | None = None,
        proposed_action_run_id: str | None = None,
        proposed_action_tenant_id: str | None = None,
        target_merchant_id: str = "merchant-phase34",
        raise_interrupt: bool = False,
    ) -> None:
        self.interrupt_run_id = interrupt_run_id
        self.checkpoint_run_id = checkpoint_run_id
        self.proposed_action_run_id = proposed_action_run_id
        self.proposed_action_tenant_id = proposed_action_tenant_id
        self.target_merchant_id = target_merchant_id
        self.raise_interrupt = raise_interrupt
        self.calls: list[tuple[object, dict]] = []
        self.state_calls: list[dict] = []

    async def ainvoke(self, input_state, config):
        self.calls.append((input_state, config))
        interrupt = FakeInterrupt(await self._interrupt_payload(input_state, config))
        if self.raise_interrupt:
            raise FakeGraphInterrupt([interrupt])
        return {"__interrupt__": [interrupt]}

    async def aget_state(self, config):
        self.state_calls.append(config)
        return FakeStateSnapshot(
            {
                "current_run_id": self.checkpoint_run_id,
                "trace_steps": [_trace("assess_risk_and_approval")],
            }
        )

    async def _interrupt_payload(self, input_state, config) -> dict:
        evidence_ref = _evidence_ref(input_state["tenant_id"], "ORD-2024-001")
        action_run_id = self.proposed_action_run_id or input_state["current_run_id"]
        action_tenant_id = self.proposed_action_tenant_id or input_state["tenant_id"]
        proposed_action = {
            "schema_version": PROPOSED_ACTION_SCHEMA_VERSION,
            "tenant_id": action_tenant_id,
            "run_id": action_run_id,
            "action_id": f"act:{action_run_id}:issue_coupon:ORD-2024-001",
            "action_type": "issue_coupon",
            "target_type": "order",
            "target_id": "ORD-2024-001",
            "amount": "600.00",
            "currency": "CNY",
            "args": {"risk_level": "high", "rule_ref": "RISK-COMP-001"},
            "reason": "Compensation amount exceeds threshold.",
            "evidence_refs": [evidence_ref.model_dump(mode="json", exclude_none=True)],
        }
        action_payload_hash = compute_action_payload_hash(proposed_action)
        snapshot = await persist_action_safety_snapshot(
            config["configurable"]["session"],
            tenant_id=UUID(input_state["tenant_id"]),
            run_id=UUID(input_state["current_run_id"]),
            proposed_action=proposed_action,
            action_payload_hash=action_payload_hash,
            policy_config_version="approval-policy.v1",
            risk_config_version="risk-rules.v1",
            retrieval_config_version=evidence_ref.retrieval_config_version,
            evidence_refs=[evidence_ref],
            created_at=_fixed_ms_now(),
            created_by=UUID(input_state["user_id"]),
        )
        payload = {
            "proposed_action": proposed_action,
            "action_payload_hash": snapshot.action_payload_hash,
            "safety_snapshot_ref": snapshot.safety_snapshot_ref,
            "safety_snapshot_hash": snapshot.safety_snapshot_hash,
            "policy_config_version": "approval-policy.v1",
            "risk_config_version": "risk-rules.v1",
            "retrieval_config_version": evidence_ref.retrieval_config_version,
            "evidence_refs": [evidence_ref.model_dump(mode="json", exclude_none=True)],
            "risk_level": "high",
            "risk_reason": "Compensation amount exceeds threshold.",
            "risk_rule_ref": "RISK-COMP-001",
            "expires_at": datetime.now(UTC).isoformat(),
        }
        payload.update(
            _phase34_interrupt_bindings(
                input_state=input_state,
                proposed_action=proposed_action,
                action_payload_hash=snapshot.action_payload_hash,
                evidence_ref=evidence_ref.model_dump(mode="json", exclude_none=True),
                target_merchant_id=self.target_merchant_id,
            )
        )
        if self.interrupt_run_id is not None:
            payload["run_id"] = self.interrupt_run_id
        return payload


class CancelledGraph:
    async def astream(self, input_state, config, stream_mode):
        raise asyncio.CancelledError("client disconnected")
        yield


class SlowGraph:
    async def astream(self, input_state, config, stream_mode):
        await asyncio.sleep(0.05)
        yield ("receive_request", {"trace_steps": []})


class GatedLifecycleGraph:
    def __init__(self) -> None:
        self.allow_completion = asyncio.Event()

    async def astream_events(self, input_state, config, version):
        yield _node_lifecycle_event("on_chain_start", "investigate", 1, {})
        await self.allow_completion.wait()
        trace_steps = [
            {
                "node": "investigate",
                "status": "completed",
                "started_at": datetime.now(UTC).isoformat(),
                "completed_at": datetime.now(UTC).isoformat(),
            }
        ]
        yield _node_lifecycle_event("on_chain_end", "investigate", 1, {"trace_steps": trace_steps})
        yield _node_lifecycle_event("on_chain_start", "final_response", 2, {})
        final_output = {"final_response": "done", "trace_steps": trace_steps}
        yield _node_lifecycle_event("on_chain_end", "final_response", 2, final_output)
        yield {
            "event": "on_chain_end",
            "name": "LangGraph",
            "metadata": {},
            "data": {"output": final_output},
        }


class MissingFinalResponseGraph:
    async def astream(self, input_state, config, stream_mode):
        yield (
            "assess_risk_and_approval",
            {
                "current_intent": "refund_troubleshooting",
                "recommendation_draft": {
                    "recommended_action": "manual_review",
                    "reasoning_summary": "退款链路需要人工核实。",
                    "evidence_refs": [
                        {
                            "doc_key": "refund_policy",
                            "chunk_id": "refund_policy_001",
                            "title": "退款规则",
                            "section": "超时处理",
                            "confidence": 0.9,
                        }
                    ],
                    "confidence": 0.8,
                },
                "risk_assessment": {
                    "risk_level": "low",
                    "risk_reason": "No customer compensation proposed.",
                    "approval_required": False,
                },
                "trace_steps": [
                    {
                        "node": "assess_risk_and_approval",
                        "status": "completed",
                        "started_at": datetime.now(UTC).isoformat(),
                        "completed_at": datetime.now(UTC).isoformat(),
                    }
                ],
            },
        )


class RagClaimSummaryGraph:
    async def astream(self, input_state, config, stream_mode):
        del input_state, config, stream_mode
        safe_ref = _rag_evidence_ref("tenant-001", "policy-safe")
        candidate_only_ref = _rag_evidence_ref("tenant-001", "candidate-only")
        state = {
            "rag_context_status": "verified",
            "verified_evidence_package": {
                "schema_version": "verified_evidence_package.v1",
                "package_id": "pkg-safe",
                "status": "verified",
                "evidence_map": {safe_ref["evidence_id"]: safe_ref},
                "prompt_projection": {"safe_refs": [safe_ref["evidence_id"]]},
                "verifier_projection": {"raw_semantic": "RAW_SEMANTIC_SHOULD_NOT_LEAK"},
                "debug_projection": {"debug_projection": "DEBUG_PROJECTION_SHOULD_NOT_LEAK"},
                "rejected_candidate_refs": [candidate_only_ref],
                "stale_refs": [],
                "conflict_refs": [],
            },
            "claim_verification_bundle": {
                "schema_version": "claim_verification_bundle.v1",
                "overall_status": "blocked",
                "route": "final_response",
                "blocked_claims": ["claim-action-1"],
                "safe_support_refs": [safe_ref, candidate_only_ref],
                "verifier_projection": "VERIFIER_PROJECTION_SHOULD_NOT_LEAK",
            },
            "blocked_claims": ["claim-action-1"],
            "safe_support_refs": [safe_ref, candidate_only_ref],
            "trace_steps": [_trace("claim_verify")],
        }
        yield ("claim_verify", state)
        yield (
            "final_response",
            {
                **state,
                "final_response": "done",
                "trace_steps": [*_trace_steps(state), _trace("final_response")],
            },
        )


class FakeInterrupt:
    def __init__(self, value: dict):
        self.value = value


class StreamInterruptGraph:
    def __init__(
        self,
        *,
        proposed_action_run_id: str | None = None,
        proposed_action_tenant_id: str | None = None,
        target_merchant_id: str = "merchant-phase34",
    ) -> None:
        self.proposed_action_run_id = proposed_action_run_id
        self.proposed_action_tenant_id = proposed_action_tenant_id
        self.target_merchant_id = target_merchant_id

    async def astream(self, input_state, config, stream_mode):
        evidence_ref = EvidenceRefV1.build(
            tenant_id=input_state["tenant_id"],
            doc_key="refund_policy",
            chunk_id="refund_policy_001",
            policy_version="v1",
            text="Compensation above 500 CNY requires approval.",
            retrieved_at=_fixed_ms_iso_z(),
            retrieval_config_version="retrieval.v1",
            rank=1,
        )
        action_run_id = self.proposed_action_run_id or input_state["current_run_id"]
        action_tenant_id = self.proposed_action_tenant_id or input_state["tenant_id"]
        proposed_action = {
            "schema_version": PROPOSED_ACTION_SCHEMA_VERSION,
            "tenant_id": action_tenant_id,
            "run_id": action_run_id,
            "action_id": f"act:{action_run_id}:issue_coupon:ORD-2024-001",
            "action_type": "issue_coupon",
            "target_type": "order",
            "target_id": "ORD-2024-001",
            "amount": "600.00",
            "currency": "CNY",
            "args": {"risk_level": "high", "rule_ref": "RISK-COMP-001"},
            "reason": "Compensation amount exceeds threshold.",
            "evidence_refs": [evidence_ref.model_dump(mode="json", exclude_none=True)],
        }
        action_payload_hash = compute_action_payload_hash(proposed_action)
        snapshot = await persist_action_safety_snapshot(
            config["configurable"]["session"],
            tenant_id=UUID(input_state["tenant_id"]),
            run_id=UUID(input_state["current_run_id"]),
            proposed_action=proposed_action,
            action_payload_hash=action_payload_hash,
            policy_config_version="approval-policy.v1",
            risk_config_version="risk-rules.v1",
            retrieval_config_version=evidence_ref.retrieval_config_version,
            evidence_refs=[evidence_ref],
            created_at=_fixed_ms_now(),
            created_by=UUID(input_state["user_id"]),
        )
        yield (
            "assess_risk_and_approval",
            {
                "risk_assessment": {
                    "risk_level": "high",
                    "risk_reason": "Compensation amount exceeds threshold.",
                    "approval_required": True,
                    "rule_ref": "RISK-COMP-001",
                },
                "proposed_action": proposed_action,
                "action_payload_hash": snapshot.action_payload_hash,
                "safety_snapshot_ref": snapshot.safety_snapshot_ref,
                "safety_snapshot_hash": snapshot.safety_snapshot_hash,
                "safety_snapshot_verified": True,
                "policy_config_version": "approval-policy.v1",
                "risk_config_version": "risk-rules.v1",
                "retrieval_config_version": evidence_ref.retrieval_config_version,
                "evidence_refs": [evidence_ref.model_dump(mode="json", exclude_none=True)],
                "trace_steps": [
                    {
                        "node": "assess_risk_and_approval",
                        "status": "completed",
                        "started_at": datetime.now(UTC).isoformat(),
                        "completed_at": datetime.now(UTC).isoformat(),
                    }
                ],
            },
        )
        yield (
            "__interrupt__",
            (
                FakeInterrupt(
                    {
                        "proposed_action": proposed_action,
                        "action_payload_hash": snapshot.action_payload_hash,
                        "safety_snapshot_ref": snapshot.safety_snapshot_ref,
                        "safety_snapshot_hash": snapshot.safety_snapshot_hash,
                        "policy_config_version": "approval-policy.v1",
                        "risk_config_version": "risk-rules.v1",
                        "retrieval_config_version": evidence_ref.retrieval_config_version,
                        "evidence_refs": [evidence_ref.model_dump(mode="json", exclude_none=True)],
                        "risk_level": "high",
                        "risk_reason": "Compensation amount exceeds threshold.",
                        "risk_rule_ref": "RISK-COMP-001",
                        "expires_at": datetime.now(UTC).isoformat(),
                        **_phase34_interrupt_bindings(
                            input_state=input_state,
                            proposed_action=proposed_action,
                            action_payload_hash=snapshot.action_payload_hash,
                            evidence_ref=evidence_ref.model_dump(mode="json", exclude_none=True),
                            target_merchant_id=self.target_merchant_id,
                        ),
                    }
                ),
            ),
        )


def _fixed_ms_now() -> datetime:
    now = datetime.now(UTC)
    return now.replace(microsecond=(now.microsecond // 1000) * 1000)


def _fixed_ms_iso_z() -> str:
    now = _fixed_ms_now()
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"


def _evidence_ref(tenant_id: str, order_id: str) -> EvidenceRefV1:
    return EvidenceRefV1.build(
        tenant_id=tenant_id,
        doc_key="refund_policy",
        chunk_id=f"refund_policy_{order_id}",
        policy_version="v1",
        text=f"Policy evidence for {order_id}.",
        retrieved_at=_fixed_ms_iso_z(),
        retrieval_config_version="retrieval.v1",
        rank=1,
    )


def _phase34_interrupt_bindings(
    *,
    input_state: dict,
    proposed_action: dict,
    action_payload_hash: str,
    evidence_ref: dict,
    target_merchant_id: str,
) -> dict:
    business_fact_ref = BusinessFactRefV1(
        tenant_id=input_state["tenant_id"],
        source_system="business_fact_service",
        resource_type="order",
        resource_id=proposed_action["target_id"],
        resource_version="order.v1",
        data_freshness_at=_fixed_ms_now(),
        retrieved_at=_fixed_ms_now(),
    ).model_dump(mode="json")
    risk_decision = {
        "schema_version": "risk_decision.v1",
        "tenant_id": input_state["tenant_id"],
        "run_id": input_state["current_run_id"],
        "action_id": proposed_action["action_id"],
        "action_payload_hash": action_payload_hash,
        "risk_level": "high",
        "reason_codes": ["approval_required", "amount_threshold"],
        "policy_config_version": "approval-policy.v1",
        "risk_config_version": "risk-rules.v1",
        "approval_required": True,
        "evaluated_at": _fixed_ms_iso_z(),
        "risk_rule_ref": "RISK-COMP-001",
        "risk_reason": "Compensation amount exceeds threshold.",
    }
    return {
        "approval_plan": {
            "schema_version": "approval_plan.v1",
            "approval_required": True,
            "route": "approval_gate",
            "policy_id": "default-approval-policy",
            "risk_level": "high",
            "reason_codes": ["approval_required", "amount_threshold"],
            "approval_idempotency_key": f"approval:{input_state['tenant_id']}:{input_state['current_run_id']}",
        },
        "target_merchant_id": target_merchant_id,
        "target_merchant_ref": {
            "schema_version": "target_merchant_binding.v1",
            "target_merchant_id": target_merchant_id,
            "source": "business_fact_ref",
            "business_fact_ref": business_fact_ref,
        },
        "business_fact_refs": [business_fact_ref],
        "verified_evidence_refs": [evidence_ref],
        "claim_verification_ref": None,
        "claim_verification_summary": {
            "schema_version": "claim_verification_summary.v1",
            "overall_status": "verified",
            "safe_support_ref_count": 1,
            "blocked_claim_count": 0,
            "reason_codes": [],
        },
        "risk_decision_ref": f"risk_decision:{input_state['current_run_id']}:r1",
        "risk_decision": risk_decision,
        "approval_idempotency_key": f"approval:{input_state['tenant_id']}:{input_state['current_run_id']}",
        "verified_evidence_package": {
            "schema_version": "verified_evidence_package.v1",
            "debug_projection": "RAW_PACKAGE_SHOULD_NOT_LEAK",
        },
        "claim_verification_bundle": {
            "schema_version": "claim_verification_bundle.v1",
            "verifier_debug": "CLAIM_VERIFIER_DEBUG_SHOULD_NOT_LEAK",
        },
        "prompt_authority_body": "PROMPT_AUTHORITY_SHOULD_NOT_LEAK",
        "safety_snapshot": {"snapshot_json": "FULL_SAFETY_SNAPSHOT_SHOULD_NOT_LEAK"},
        "action_authority_body": {"args": {"internal": "ACTION_AUTHORITY_SHOULD_NOT_LEAK"}},
    }


def _trace(node: str) -> dict:
    return {
        "node": node,
        "status": "completed",
        "started_at": datetime.now(UTC).isoformat(),
        "completed_at": datetime.now(UTC).isoformat(),
    }


def _trace_steps(state: dict) -> list[dict]:
    trace_steps = state.get("trace_steps")
    return list(trace_steps) if isinstance(trace_steps, list) else []


def _rag_evidence_ref(tenant_id: str, suffix: str) -> dict[str, str]:
    return {
        "schema_version": "evidence_ref.v1",
        "tenant_id": tenant_id,
        "evidence_id": f"refund_policy/{suffix}@v1",
        "doc_key": "refund_policy",
        "chunk_id": suffix,
        "policy_version": "v1",
        "text_hash": f"sha256:{suffix}",
        "retrieved_at": "2026-06-28T00:00:00+00:00",
        "retrieval_config_version": "retrieval.v1",
    }


INVESTIGATION_RESPONSE_FIELDS = {
    "investigation_result",
    "investigation_steps",
    "investigation_trigger_reason",
    "investigation_path",
}
FORBIDDEN_MEMORY_METADATA_KEYS = {
    "raw_payload",
    "private_reasoning",
    "approval_authority_body",
    "action_authority_body",
    "debug_trace",
    "snapshot",
    "hash",
    "secret",
}
RAG_CLAIM_SUMMARY_KEYS = {
    "schema_version",
    "rag_context_status",
    "verified_evidence_count",
    "rejected_candidate_count",
    "stale_ref_count",
    "conflict_ref_count",
    "claim_verification_status",
    "blocked_claim_count",
    "safe_support_ref_count",
}


def _auth_header(user: User, scopes: list[str]) -> dict[str, str]:
    token = create_access_token(
        {
            "sub": str(user.id),
            "tenant_id": str(user.tenant_id),
            "role": user.role,
            "scopes": scopes,
        }
    )
    return {"Authorization": f"Bearer {token}"}


async def _create_same_tenant_role_user(session: AsyncSession, seeded_session: dict, role: str) -> User:
    user = User(
        id=uuid4(),
        tenant_id=seeded_session["tenant"].id,
        merchant_id=seeded_session["merchant"].id,
        username=f"{role}_{uuid4().hex[:8]}",
        password_hash=hash_password("moca2024"),
        role=role,
        is_active=True,
    )
    session.add(user)
    await session.flush()
    return user


def _stream_input(run: AgentRun, user: User) -> dict[str, str]:
    return {
        "user_query": run.input_query,
        "thread_id": run.thread_id,
        "tenant_id": str(user.tenant_id),
        "user_id": str(user.id),
        "role": user.role,
        "current_run_id": str(run.id),
    }


async def _create_run(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    user_id: UUID,
    final_status: str = "pending",
) -> AgentRun:
    run_id = uuid4()
    now = datetime.now(UTC)
    return await write_agent_run(
        session,
        run_id=str(run_id),
        thread_id=f"sse-{run_id}",
        tenant_id=str(tenant_id),
        user_id=str(user_id),
        input_query="SSE duplicate guard test",
        final_status=final_status,
        final_response=None,
        started_at=now,
        completed_at=None,
        total_latency_ms=None,
    )


def _event_data(event: dict) -> dict:
    return json.loads(event["data"])


async def _run_agent_run_stream(client: AsyncClient, run_id: str, user: User) -> list[dict]:
    response = await client.get(
        f"/api/v1/agent-runs/{run_id}/events",
        headers=_auth_header(user, ["agent:chat"]),
    )
    assert response.status_code == 200
    events: list[dict] = []
    for line in response.text.splitlines():
        if not line.startswith("data: "):
            continue
        events.append(json.loads(line.removeprefix("data: ")))
    return events


async def _messages_for_run(session: AsyncSession, *, run_id: UUID, role: str | None = None) -> list[ConversationMessage]:
    filters = [ConversationMessage.run_id == run_id, ConversationMessage.deleted_at.is_(None)]
    if role is not None:
        filters.append(ConversationMessage.role == role)
    result = await session.execute(select(ConversationMessage).where(*filters).order_by(ConversationMessage.message_index))
    return list(result.scalars().all())


async def _count_rows(session: AsyncSession, model, *filters) -> int:
    result = await session.execute(select(func.count()).select_from(model).where(*filters))
    return int(result.scalar_one())


def _node_lifecycle_event(event_type: str, node_name: str, step_index: int, output: dict) -> dict:
    return {
        "event": event_type,
        "name": node_name,
        "metadata": {
            "langgraph_node": node_name,
            "langgraph_step": step_index,
            "langgraph_checkpoint_ns": f"{node_name}:test",
        },
        "data": {"output": output},
    }


def _assert_no_investigation_fields(payload: dict) -> None:
    assert INVESTIGATION_RESPONSE_FIELDS.isdisjoint(payload)
    serialized = json.dumps(payload, ensure_ascii=False)
    for field in INVESTIGATION_RESPONSE_FIELDS:
        assert field not in serialized


def test_extract_step_payload_counts_v2_evidence_refs():
    payload = _extract_step_payload(
        "investigate",
        {
            "retrieved_evidence": {
                "schema_version": "knowledge_search_result.v2",
                "evidence_refs": [
                    {"evidence_id": "refund_policy/refund_policy_001@v1"},
                    {"evidence_id": "refund_policy/refund_policy_001@v2"},
                ],
            }
        },
    )

    assert payload["evidence_count"] == 2


def test_sse_event_projects_target_node_name_without_rewriting_legacy_node_name():
    event = _sse_event(
        event_type="step_completed",
        run_id="run-graph-projection",
        step_index=2,
        node_name="extract_slots",
        status="completed",
        message="done",
        payload={"tool_name": "slot_parser"},
    )

    data = json.loads(event["data"])

    assert data["node_name"] == "extract_slots"
    assert data["target_node_name"] == "slot_resolution_gate"
    assert data["payload"] == {"tool_name": "slot_parser"}


@pytest.mark.asyncio
async def test_event_generator_projects_allowlisted_rag_claim_summary_in_step_payload(
    session: AsyncSession,
    seeded_session,
):
    user = seeded_session["users"]["cs_zhang"]
    run = await _create_run(session, tenant_id=user.tenant_id, user_id=user.id, final_status="running")
    await session.commit()

    events = [
        _event_data(event)
        async for event in _event_generator(
            RagClaimSummaryGraph(),
            _stream_input(run, user),
            {"configurable": {"thread_id": run.thread_id, "session": session}},
            run=run,
            session=session,
            user=user,
        )
        if "data" in event
    ]
    claim_event = next(event for event in events if event.get("node_name") == "claim_verify")
    summary = claim_event["payload"]["rag_claim_summary"]

    assert set(summary) == RAG_CLAIM_SUMMARY_KEYS
    assert summary == {
        "schema_version": "rag_claim_summary.v1",
        "rag_context_status": "verified",
        "verified_evidence_count": 1,
        "rejected_candidate_count": 1,
        "stale_ref_count": 0,
        "conflict_ref_count": 0,
        "claim_verification_status": "blocked",
        "blocked_claim_count": 1,
        "safe_support_ref_count": 1,
    }
    serialized = json.dumps(claim_event["payload"], ensure_ascii=False)
    for forbidden in (
        "verified_evidence_package",
        "claim_verification_bundle",
        "RAW_SEMANTIC_SHOULD_NOT_LEAK",
        "DEBUG_PROJECTION_SHOULD_NOT_LEAK",
        "VERIFIER_PROJECTION_SHOULD_NOT_LEAK",
        "candidate-only",
    ):
        assert forbidden not in serialized


def test_dedupe_evidence_refs_preserves_policy_versions():
    refs = _dedupe_evidence_refs(
        [
            [
                {
                    "evidence_id": "refund_policy/refund_policy_001@v1",
                    "chunk_id": "refund_policy_001",
                },
                {
                    "evidence_id": "refund_policy/refund_policy_001@v2",
                    "chunk_id": "refund_policy_001",
                },
            ]
        ]
    )

    assert [ref["evidence_id"] for ref in refs] == [
        "refund_policy/refund_policy_001@v1",
        "refund_policy/refund_policy_001@v2",
    ]
    assert all("text" not in ref for ref in refs)


def test_dedupe_evidence_refs_drops_later_display_projection_duplicate():
    refs = _dedupe_evidence_refs(
        [
            [
                {
                    "evidence_id": "refund_policy/refund_policy_001@v1",
                    "doc_key": "refund_policy",
                    "chunk_id": "refund_policy_001",
                    "score": 0.91,
                }
            ],
            [
                {
                    "doc_key": "refund_policy",
                    "chunk_id": "refund_policy_001",
                    "title": "退款规则",
                }
            ],
        ]
    )

    assert refs == [
        {
            "evidence_id": "refund_policy/refund_policy_001@v1",
            "doc_key": "refund_policy",
            "chunk_id": "refund_policy_001",
            "score": 0.91,
        }
    ]


@pytest.mark.asyncio
async def test_events_rejects_already_started_run_with_409(
    client: AsyncClient,
    session: AsyncSession,
    seeded_session,
    monkeypatch,
):
    user = seeded_session["users"]["cs_zhang"]
    run = await _create_run(session, tenant_id=user.tenant_id, user_id=user.id, final_status="running")
    await session.commit()
    graph = NeverCalledGraph()
    monkeypatch.setattr(app.state, "agent_graph", graph, raising=False)

    response = await client.get(
        f"/api/v1/agent-runs/{run.id}/events",
        headers=_auth_header(user, ["agent:chat"]),
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "RUN_ALREADY_STARTED"
    assert graph.calls == []


@pytest.mark.asyncio
async def test_events_rejects_terminal_run_with_409(
    client: AsyncClient,
    session: AsyncSession,
    seeded_session,
    monkeypatch,
):
    user = seeded_session["users"]["cs_zhang"]
    run = await _create_run(session, tenant_id=user.tenant_id, user_id=user.id, final_status="completed")
    await session.commit()
    graph = NeverCalledGraph()
    monkeypatch.setattr(app.state, "agent_graph", graph, raising=False)

    response = await client.get(
        f"/api/v1/agent-runs/{run.id}/events",
        headers=_auth_header(user, ["agent:chat"]),
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "RUN_ALREADY_STARTED"
    assert graph.calls == []


@pytest.mark.asyncio
async def test_create_agent_run_persists_exactly_one_user_message(
    client: AsyncClient,
    session: AsyncSession,
    seeded_session,
    monkeypatch,
):
    user = seeded_session["users"]["cs_zhang"]
    graph = CaptureConfigGraph()
    monkeypatch.setattr(app.state, "agent_graph", graph, raising=False)

    response = await client.post(
        "/api/v1/agent-runs",
        json={"query": "订单 ORD-TEST-001 的退款进度如何？", "thread_id": f"phase24-create-{uuid4()}"},
        headers=_auth_header(user, ["agent:chat"]),
    )

    assert response.status_code == 200
    run_id = UUID(response.json()["data"]["run_id"])
    user_messages = await _messages_for_run(session, run_id=run_id, role="user")
    assert len(user_messages) == 1
    assert user_messages[0].role == "user"
    assert user_messages[0].run_id == run_id
    assert user_messages[0].content == "订单 ORD-TEST-001 的退款进度如何？"

    await _run_agent_run_stream(client, str(run_id), user)
    duplicate_response = await client.get(
        f"/api/v1/agent-runs/{run_id}/events",
        headers=_auth_header(user, ["agent:chat"]),
    )
    assert duplicate_response.status_code == 409
    assert len(await _messages_for_run(session, run_id=run_id, role="user")) == 1


@pytest.mark.asyncio
async def test_agent_run_stream_passes_conversation_ids_to_graph_and_tools(
    client: AsyncClient,
    session: AsyncSession,
    seeded_session,
    monkeypatch,
):
    user = seeded_session["users"]["cs_zhang"]
    graph = CaptureConfigGraph()
    monkeypatch.setattr(app.state, "agent_graph", graph, raising=False)
    response = await client.post(
        "/api/v1/agent-runs",
        json={"query": "帮我查一下订单 ORD-TEST-001", "thread_id": f"phase24-config-{uuid4()}"},
        headers=_auth_header(user, ["agent:chat"]),
    )
    assert response.status_code == 200
    run_id = UUID(response.json()["data"]["run_id"])

    user_messages = await _messages_for_run(session, run_id=run_id, role="user")
    assert len(user_messages) == 1
    await _run_agent_run_stream(client, str(run_id), user)

    assert len(graph.calls) == 1
    _, config = graph.calls[0]
    configurable = config["configurable"]
    assert configurable["conversation_thread_id"] == str(user_messages[0].conversation_thread_id)
    assert configurable["conversation_message_id"] == str(user_messages[0].id)


@pytest.mark.asyncio
async def test_agent_run_stream_graph_config_contains_canonical_trusted_context(
    client: AsyncClient,
    seeded_session,
    monkeypatch,
):
    user = seeded_session["users"]["cs_zhang"]
    graph = CaptureConfigGraph()
    monkeypatch.setattr(app.state, "agent_graph", graph, raising=False)
    payload_override = {"permissions": ["tool:get_order"], "merchant_scope": {"merchant_ids": ["*"]}}

    response = await client.post(
        "/api/v1/agent-runs",
        json={
            "query": "帮我查一下订单 ORD-TEST-001",
            "thread_id": f"phase27-trusted-config-{uuid4()}",
            **payload_override,
        },
        headers=_auth_header(user, ["agent:chat", "orders:read", "knowledge:read"]),
    )
    assert response.status_code == 200
    run_id = UUID(response.json()["data"]["run_id"])

    await _run_agent_run_stream(client, str(run_id), user)

    assert len(graph.calls) == 1
    input_state, config = graph.calls[0]
    configurable = config["configurable"]
    trusted_context = TrustedContext.model_validate(configurable["trusted_context"])
    legacy_identity = project_to_legacy_agent_state_identity(trusted_context)
    assert trusted_context.schema_version == "trusted_context.v1"
    assert trusted_context.run_id == str(run_id)
    assert trusted_context.session_id is None
    assert trusted_context.thread_id == input_state["thread_id"]
    assert trusted_context.trace_id == configurable["trace_id"]
    assert "current_run_id" not in trusted_context.model_dump()
    assert input_state["current_run_id"] == legacy_identity["current_run_id"]
    assert configurable["permissions"] == trusted_context.permissions
    assert configurable["merchant_scope"] == trusted_context.merchant_scope.model_dump(mode="json")


@pytest.mark.asyncio
async def test_agent_run_stream_fails_closed_when_user_message_missing(
    client: AsyncClient,
    session: AsyncSession,
    seeded_session,
    monkeypatch,
):
    user = seeded_session["users"]["cs_zhang"]
    run = await _create_run(
        session,
        tenant_id=user.tenant_id,
        user_id=user.id,
        final_status="pending",
    )
    await session.commit()
    graph = NeverCalledGraph()
    monkeypatch.setattr(app.state, "agent_graph", graph, raising=False)

    response = await client.get(
        f"/api/v1/agent-runs/{run.id}/events",
        headers=_auth_header(user, ["agent:chat"]),
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "RUN_CONVERSATION_MESSAGE_MISSING"
    assert graph.calls == []
    await session.refresh(run)
    assert run.final_status == "error"
    assert run.error_summary == "RUN_CONVERSATION_MESSAGE_MISSING"
    assert run.completed_at is not None


@pytest.mark.asyncio
async def test_completed_agent_run_persists_exactly_one_assistant_message(
    client: AsyncClient,
    session: AsyncSession,
    seeded_session,
    monkeypatch,
):
    user = seeded_session["users"]["cs_zhang"]
    monkeypatch.setattr(app.state, "agent_graph", CaptureConfigGraph(), raising=False)
    response = await client.post(
        "/api/v1/agent-runs",
        json={"query": "给我一个完成答复", "thread_id": f"phase24-assistant-{uuid4()}"},
        headers=_auth_header(user, ["agent:chat"]),
    )
    assert response.status_code == 200
    run_id = UUID(response.json()["data"]["run_id"])

    await _run_agent_run_stream(client, str(run_id), user)

    assistant_messages = await _messages_for_run(session, run_id=run_id, role="assistant")
    assert len(assistant_messages) == 1
    assert assistant_messages[0].content == "done"
    assert assistant_messages[0].metadata_json["status"] == "completed"
    assert assistant_messages[0].metadata_json["source"] == "agent_runs.finalizer"
    assert not (set(assistant_messages[0].metadata_json) & FORBIDDEN_MEMORY_METADATA_KEYS)
    finalizer_step = (
        await session.execute(
            select(AgentStep).where(AgentStep.run_id == run_id, AgentStep.node_name == "agent_run_memory_finalize")
        )
    ).scalar_one()
    metrics = finalizer_step.metrics_json or {}
    assert metrics["assistant_message_id"] == str(assistant_messages[0].id)
    assert metrics["memory_write_status"] in {"completed", "skipped", "error", "failed"}
    assert not (set(metrics) & FORBIDDEN_MEMORY_METADATA_KEYS)


@pytest.mark.asyncio
async def test_completed_agent_run_updates_thread_summary_idempotently(
    client: AsyncClient,
    session: AsyncSession,
    seeded_session,
    monkeypatch,
):
    user = seeded_session["users"]["cs_zhang"]
    tenant_id = user.tenant_id
    monkeypatch.setattr(app.state, "agent_graph", CaptureConfigGraph(), raising=False)
    response = await client.post(
        "/api/v1/agent-runs",
        json={"query": "总结这个回合", "thread_id": f"phase24-summary-{uuid4()}"},
        headers=_auth_header(user, ["agent:chat"]),
    )
    assert response.status_code == 200
    run_id = UUID(response.json()["data"]["run_id"])

    await _run_agent_run_stream(client, str(run_id), user)
    duplicate_response = await client.get(
        f"/api/v1/agent-runs/{run_id}/events",
        headers=_auth_header(user, ["agent:chat"]),
    )
    assert duplicate_response.status_code == 409

    summaries = (
        (
            await session.execute(
                select(ConversationSummary).where(
                    ConversationSummary.tenant_id == tenant_id,
                    ConversationSummary.summary_type == "thread_rolling",
                    ConversationSummary.deleted_at.is_(None),
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(summaries) == 1
    assert str(run_id) in (summaries[0].summary_json or {}).get("source_run_ids", [str(run_id)])


@pytest.mark.asyncio
async def test_events_rejects_cross_tenant_run_before_claim(
    client: AsyncClient,
    session: AsyncSession,
    seeded_session,
    monkeypatch,
):
    user = seeded_session["users"]["cs_zhang"]
    other_user = seeded_session["users"]["other_support"]
    run = await _create_run(session, tenant_id=other_user.tenant_id, user_id=other_user.id)
    await session.commit()
    graph = NeverCalledGraph()
    monkeypatch.setattr(app.state, "agent_graph", graph, raising=False)

    response = await client.get(
        f"/api/v1/agent-runs/{run.id}/events",
        headers=_auth_header(user, ["agent:chat"]),
    )

    assert response.status_code == 404
    assert "rag_claim_summary" not in response.text
    assert graph.calls == []
    await session.refresh(run)
    assert run.final_status == "pending"


@pytest.mark.asyncio
async def test_run_visibility_supervisor_approval_manager_get_403(
    client: AsyncClient,
    session: AsyncSession,
    seeded_session,
):
    owner = seeded_session["users"]["cs_zhang"]
    run = await _create_run(session, tenant_id=owner.tenant_id, user_id=owner.id, final_status="completed")
    supervisor = await _create_same_tenant_role_user(session, seeded_session, "supervisor")
    approval_manager = await _create_same_tenant_role_user(session, seeded_session, "approval_manager")
    await session.commit()

    for viewer in (supervisor, approval_manager):
        status_response = await client.get(
            f"/api/v1/agent-runs/{run.id}",
            headers=_auth_header(viewer, ["agent:chat"]),
        )
        evidence_response = await client.get(
            f"/api/v1/agent-runs/{run.id}/evidence",
            headers=_auth_header(viewer, ["agent:chat"]),
        )

        assert status_response.status_code == 403
        assert status_response.json()["error"]["code"] == "FORBIDDEN"
        assert "rag_claim_summary" not in status_response.text
        assert evidence_response.status_code == 403
        assert evidence_response.json()["error"]["code"] == "FORBIDDEN"
        assert "rag_claim_summary" not in evidence_response.text


@pytest.mark.asyncio
async def test_run_status_response_exposes_safe_scope_metadata(
    client: AsyncClient,
    session: AsyncSession,
    seeded_session,
) -> None:
    owner = seeded_session["users"]["cs_zhang"]
    run = await _create_run(session, tenant_id=owner.tenant_id, user_id=owner.id, final_status="completed")
    run.scope_classification = BUSINESS_MERCHANT
    run.target_merchant_id = "merchant-1"
    run.target_merchant_ref = {
        "schema_version": "target_merchant_binding.v1",
        "target_merchant_id": "merchant-1",
        "source": "business_fact_ref",
        "business_fact_ref": {
            "schema_version": "business_fact_ref.v1",
            "tenant_id": str(owner.tenant_id),
            "source_system": "business_fact_service",
            "resource_type": "order",
            "resource_id": "ORD-SCOPE-1",
            "resource_version": "order.v1",
            "data_freshness_at": None,
            "retrieved_at": datetime.now(UTC).isoformat(),
        },
    }
    run.scope_source = "target_merchant_binding_v1"
    await session.commit()

    response = await client.get(f"/api/v1/agent-runs/{run.id}", headers=_auth_header(owner, ["agent:chat"]))

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["scope_classification"] == BUSINESS_MERCHANT
    assert data["target_merchant_id"] == "merchant-1"
    assert data["scope_source"] == "target_merchant_binding_v1"


def test_agent_run_visibility_guards_remain_admin_only_and_ignore_target_merchant_context():
    resolved_context = project_target_merchant_context(
        {
            "tenant_id": "tenant-001",
            "current_intent": "refund_troubleshooting",
            "last_business_context_refs": {
                "business_fact_refs": [
                    {
                        "schema_version": "business_fact_ref.v1",
                        "tenant_id": "tenant-001",
                        "source_system": "business_fact_service",
                        "resource_type": "order",
                        "resource_id": "ORD-403",
                        "resource_version": "v1",
                        "data_freshness_at": "2026-06-28T00:00:00+00:00",
                        "retrieved_at": "2026-06-28T00:00:00+00:00",
                    }
                ]
            },
        }
    )

    assert resolved_context["status"] == "resolved"
    assert ADMIN_RUN_VISIBILITY_ROLES == {"admin"}
    assert "target_merchant_context" not in inspect.getsource(_ensure_can_view_run)
    assert "target_merchant_context" not in inspect.getsource(_ensure_can_execute_run)


@pytest.mark.asyncio
async def test_run_status_evidence_and_stream_reject_non_owner_business_and_ghost_roles(
    client: AsyncClient,
    session: AsyncSession,
    seeded_session,
):
    owner = seeded_session["users"]["admin_user"]
    run = await _create_run(session, tenant_id=owner.tenant_id, user_id=owner.id, final_status="completed")
    pending_run = await _create_run(session, tenant_id=owner.tenant_id, user_id=owner.id, final_status="pending")
    support = seeded_session["users"]["cs_zhang"]
    manager = await _create_same_tenant_role_user(session, seeded_session, "manager")
    merchant = await _create_same_tenant_role_user(session, seeded_session, "merchant")
    supervisor = await _create_same_tenant_role_user(session, seeded_session, "supervisor")
    approval_manager = await _create_same_tenant_role_user(session, seeded_session, "approval_manager")
    await session.commit()

    for viewer in (support, manager, merchant, supervisor, approval_manager):
        headers = _auth_header(viewer, ["agent:chat"])
        status_response = await client.get(f"/api/v1/agent-runs/{run.id}", headers=headers)
        evidence_response = await client.get(f"/api/v1/agent-runs/{run.id}/evidence", headers=headers)
        stream_response = await client.get(f"/api/v1/agent-runs/{pending_run.id}/events", headers=headers)

        assert status_response.status_code == 403
        assert status_response.json()["error"]["code"] == "FORBIDDEN"
        assert "rag_claim_summary" not in status_response.text
        assert evidence_response.status_code == 403
        assert evidence_response.json()["error"]["code"] == "FORBIDDEN"
        assert "rag_claim_summary" not in evidence_response.text
        assert stream_response.status_code == 403
        assert stream_response.json()["error"]["code"] == "FORBIDDEN"
        assert "rag_claim_summary" not in stream_response.text

    await session.refresh(pending_run)
    assert pending_run.final_status == "pending"


@pytest.mark.asyncio
async def test_events_rejects_same_tenant_supervisor_execution_before_claim(
    client: AsyncClient,
    session: AsyncSession,
    seeded_session,
    monkeypatch,
):
    owner = seeded_session["users"]["cs_zhang"]
    supervisor = await _create_same_tenant_role_user(session, seeded_session, "supervisor")
    run = await _create_run(session, tenant_id=owner.tenant_id, user_id=owner.id)
    await session.commit()
    graph = NeverCalledGraph()
    monkeypatch.setattr(app.state, "agent_graph", graph, raising=False)

    response = await client.get(
        f"/api/v1/agent-runs/{run.id}/events",
        headers=_auth_header(supervisor, ["agent:chat"]),
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"
    assert "rag_claim_summary" not in response.text
    assert graph.calls == []
    await session.refresh(run)
    assert run.final_status == "pending"


@pytest.mark.asyncio
async def test_event_generator_marks_run_error_when_stream_is_cancelled(
    session: AsyncSession,
    seeded_session,
):
    user = seeded_session["users"]["cs_zhang"]
    run = await _create_run(session, tenant_id=user.tenant_id, user_id=user.id, final_status="running")
    await session.commit()

    generator = _event_generator(
        CancelledGraph(),
        {"user_query": run.input_query},
        {"configurable": {"thread_id": run.thread_id, "session": session}},
        run=run,
        session=session,
        user=user,
    )

    first_event = await anext(generator)
    assert '"event_type": "run_started"' in first_event["data"]
    with pytest.raises(asyncio.CancelledError):
        await anext(generator)

    await session.refresh(run)
    lifecycle_rows = (
        (
            await session.execute(
                select(AgentTraceEvent)
                .where(AgentTraceEvent.run_id == run.id, AgentTraceEvent.event_type == "run_status_changed")
                .order_by(AgentTraceEvent.sequence)
            )
        )
        .scalars()
        .all()
    )
    assert run.final_status == "error"
    assert run.completed_at is not None
    assert run.error_summary == "client disconnected"
    assert [row.redacted_payload["status"] for row in lifecycle_rows] == ["running", "error"]
    assert all(row.redacted_payload["status"] != "completed" for row in lifecycle_rows)


@pytest.mark.asyncio
async def test_event_generator_sends_keepalive_while_graph_node_is_running(
    session: AsyncSession,
    seeded_session,
    monkeypatch,
):
    monkeypatch.setattr("src.api.routers.agent_runs.SSE_HEARTBEAT_SECONDS", 0.01)
    user = seeded_session["users"]["cs_zhang"]
    run = await _create_run(session, tenant_id=user.tenant_id, user_id=user.id, final_status="running")
    await session.commit()

    generator = _event_generator(
        SlowGraph(),
        {"user_query": run.input_query},
        {"configurable": {"thread_id": run.thread_id, "session": session}},
        run=run,
        session=session,
        user=user,
    )

    try:
        first_event = await anext(generator)
        keepalive = await anext(generator)
        next_event = await anext(generator)
        while "data" not in next_event:
            next_event = await anext(generator)
    finally:
        await generator.aclose()

    assert '"event_type": "run_started"' in first_event["data"]
    assert keepalive == {"comment": "keepalive"}
    assert '"event_type": "step_started"' in next_event["data"]


@pytest.mark.asyncio
async def test_event_generator_keeps_started_event_visible_before_completion(
    session: AsyncSession,
    seeded_session,
):
    user = seeded_session["users"]["cs_zhang"]
    run = await _create_run(session, tenant_id=user.tenant_id, user_id=user.id, final_status="running")
    await session.commit()
    graph = GatedLifecycleGraph()

    generator = _event_generator(
        graph,
        {"user_query": run.input_query},
        {"configurable": {"thread_id": run.thread_id, "session": session}},
        run=run,
        session=session,
        user=user,
    )
    completion_task: asyncio.Task[dict] | None = None

    try:
        run_started = await anext(generator)
        step_started = await anext(generator)
        completion_task = asyncio.create_task(anext(generator))
        await asyncio.sleep(0.02)
        assert not completion_task.done()
        graph.allow_completion.set()
        step_completed = await asyncio.wait_for(completion_task, timeout=1)
        remaining_events = [event async for event in generator]
    finally:
        if completion_task is not None and not completion_task.done():
            completion_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await completion_task
        await generator.aclose()

    assert _event_data(run_started)["event_type"] == "run_started"
    started_data = _event_data(step_started)
    completed_data = _event_data(step_completed)
    assert started_data["event_type"] == "step_started"
    assert started_data["status"] == "running"
    assert completed_data["event_type"] == "step_completed"
    assert completed_data["status"] == "completed"
    assert completed_data["node_name"] == started_data["node_name"]
    assert any(_event_data(event)["event_type"] == "final_response" for event in remaining_events if "data" in event)


@pytest.mark.asyncio
async def test_event_generator_synthesizes_final_response_when_stream_ends_without_one(
    session: AsyncSession,
    seeded_session,
):
    user = seeded_session["users"]["cs_zhang"]
    run = await _create_run(session, tenant_id=user.tenant_id, user_id=user.id, final_status="running")
    await session.commit()

    generator = _event_generator(
        MissingFinalResponseGraph(),
        {"user_query": run.input_query},
        {"configurable": {"thread_id": run.thread_id, "session": session}},
        run=run,
        session=session,
        user=user,
    )

    final_event = None
    async for event in generator:
        if "data" in event and '"event_type": "final_response"' in event["data"]:
            final_event = event

    await session.refresh(run)
    lifecycle_rows = (
        (
            await session.execute(
                select(AgentTraceEvent)
                .where(AgentTraceEvent.run_id == run.id, AgentTraceEvent.event_type == "run_status_changed")
                .order_by(AgentTraceEvent.sequence)
            )
        )
        .scalars()
        .all()
    )
    assert final_event is not None
    final_data = _event_data(final_event)
    assert set(final_data["payload"]) == {"final_response", "target_merchant_context"}
    assert final_data["payload"]["target_merchant_context"] == {
        "schema_version": "target_merchant_context.v1",
        "status": "deferred",
        "source": "business_fact_refs",
        "reason_codes": ["TARGET_MERCHANT_CONTEXT_DEFERRED_UNTIL_BUSINESS_FACT_REF"],
    }
    _assert_no_investigation_fields(final_data)
    assert run.final_status == "completed"
    assert run.final_response is not None
    assert "退款链路需要人工核实" in run.final_response
    assert [row.redacted_payload["status"] for row in lifecycle_rows] == ["running", "completed"]


@pytest.mark.asyncio
async def test_event_generator_reports_completion_persistence_failure(
    session: AsyncSession,
    seeded_session,
    monkeypatch,
):
    async def fail_write_agent_steps(*args, **kwargs):
        raise RuntimeError("step write failed")

    monkeypatch.setattr("src.api.routers.agent_runs.write_agent_steps", fail_write_agent_steps)
    user = seeded_session["users"]["cs_zhang"]
    run = await _create_run(session, tenant_id=user.tenant_id, user_id=user.id, final_status="running")
    await session.commit()

    generator = _event_generator(
        MissingFinalResponseGraph(),
        {"user_query": run.input_query},
        {"configurable": {"thread_id": run.thread_id, "session": session}},
        run=run,
        session=session,
        user=user,
    )

    events = [event async for event in generator]

    await session.refresh(run)
    assert any("step write failed" in event.get("data", "") for event in events)
    assert any('"event_type": "error"' in event.get("data", "") for event in events)
    assert not any('"event_type": "final_response"' in event.get("data", "") for event in events)
    assert run.final_status == "error"
    assert run.final_response is None
    assert run.error_summary == "step write failed"


@pytest.mark.asyncio
async def test_event_generator_treats_stream_interrupt_node_as_approval_required(
    session: AsyncSession,
    seeded_session,
):
    user = seeded_session["users"]["cs_zhang"]
    target_merchant_id = str(seeded_session["merchant"].id)
    run = await _create_run(session, tenant_id=user.tenant_id, user_id=user.id, final_status="running")
    await session.commit()

    generator = _event_generator(
        StreamInterruptGraph(target_merchant_id=target_merchant_id),
        _stream_input(run, user),
        {"configurable": {"thread_id": run.thread_id, "session": session}},
        run=run,
        session=session,
        user=user,
    )

    approval_event = None
    async for event in generator:
        if "data" in event and '"event_type": "approval_required"' in event["data"]:
            approval_event = event

    await session.refresh(run)
    approval = (await session.execute(select(ApprovalRequest).where(ApprovalRequest.run_id == run.id))).scalar_one()
    lifecycle_rows = (
        (
            await session.execute(
                select(AgentTraceEvent)
                .where(AgentTraceEvent.run_id == run.id, AgentTraceEvent.event_type == "run_status_changed")
                .order_by(AgentTraceEvent.sequence)
            )
        )
        .scalars()
        .all()
    )
    assert approval_event is not None
    approval_data = _event_data(approval_event)
    assert {"approval_id", "proposed_action_summary", "risk_level"}.issubset(approval_data["payload"])
    assert {
        "approval_revision_refs",
        "expected_request_version",
        "expected_level_version",
        "expected_assignment_version",
        "expected_revision",
        "action_payload_hash",
        "safety_snapshot_ref",
        "safety_snapshot_hash",
        "allowed_decision_types",
        "target_merchant_id",
        "target_merchant_ref",
        "business_fact_refs",
        "verified_evidence_refs",
        "claim_verification_ref",
        "claim_verification_summary",
        "risk_decision_ref",
        "risk_decision_summary",
    }.issubset(approval_data["payload"])
    assert approval_data["payload"]["proposed_action_summary"] == {
        "action_id": f"act:{run.id}:issue_coupon:ORD-2024-001",
        "action_type": "issue_coupon",
        "target_type": "order",
        "target_id": "ORD-2024-001",
        "amount": "600.00",
        "currency": "CNY",
        "reason": "Compensation amount exceeds threshold.",
    }
    assert approval_data["payload"]["target_merchant_id"] == target_merchant_id
    assert approval_data["payload"]["target_merchant_ref"]["target_merchant_id"] == target_merchant_id
    assert approval_data["payload"]["business_fact_refs"][0]["resource_id"] == "ORD-2024-001"
    assert approval_data["payload"]["verified_evidence_refs"][0]["evidence_id"] == "refund_policy/refund_policy_001@v1"
    assert approval_data["payload"]["claim_verification_ref"] is None
    assert approval_data["payload"]["claim_verification_summary"]["overall_status"] == "verified"
    assert approval_data["payload"]["risk_decision_ref"] == f"risk_decision:{run.id}:r1"
    assert approval_data["payload"]["risk_decision_summary"] == {
        "schema_version": "risk_decision_summary.v1",
        "risk_level": "high",
        "reason_codes": ["approval_required", "amount_threshold"],
        "approval_required": True,
        "risk_rule_ref": "RISK-COMP-001",
    }
    assert approval_data["payload"]["allowed_decision_types"] == [
        "accept",
        "approve",
        "edit",
        "respond",
        "reject",
        "ignore",
    ]
    for forbidden_key in (
        "proposed_action",
        "approval_plan",
        "risk_decision",
        "approval_idempotency_key",
        "verified_evidence_package",
        "claim_verification_bundle",
        "prompt_authority_body",
        "safety_snapshot",
        "action_authority_body",
    ):
        assert forbidden_key not in approval_data["payload"]
    serialized_payload = json.dumps(approval_data["payload"], ensure_ascii=False)
    for forbidden in (
        "RAW_PACKAGE_SHOULD_NOT_LEAK",
        "CLAIM_VERIFIER_DEBUG_SHOULD_NOT_LEAK",
        "PROMPT_AUTHORITY_SHOULD_NOT_LEAK",
        "FULL_SAFETY_SNAPSHOT_SHOULD_NOT_LEAK",
        "ACTION_AUTHORITY_SHOULD_NOT_LEAK",
        '"args"',
    ):
        assert forbidden not in serialized_payload
    _assert_no_investigation_fields(approval_data)
    assert '"status": "waiting_approval"' in approval_event["data"]
    assert run.final_status == "interrupted"
    assert run.final_response is None
    assert approval.status == "pending"
    assert approval.risk_level == "high"
    assert approval.proposed_action["amount"] == "600.00"
    assert approval.target_merchant_id == target_merchant_id
    assert approval.target_merchant_ref["target_merchant_id"] == target_merchant_id
    assert approval.business_fact_refs[0]["resource_id"] == "ORD-2024-001"
    assert approval.verified_evidence_refs[0]["evidence_id"] == "refund_policy/refund_policy_001@v1"
    assert approval.claim_verification_ref is None
    assert approval.claim_verification_summary == {
        "schema_version": "claim_verification_summary.v1",
        "overall_status": "verified",
        "safe_support_ref_count": 1,
        "blocked_claim_count": 0,
        "reason_codes": [],
    }
    assert approval.risk_decision_ref == f"risk_decision:{run.id}:r1"
    assert approval.risk_decision["action_payload_hash"] == approval.action_payload_hash
    assert approval.approval_idempotency_key == f"approval:{user.tenant_id}:{run.id}"
    assert [row.redacted_payload["status"] for row in lifecycle_rows] == ["running", "interrupted"]


@pytest.mark.parametrize(
    ("spoof_field", "expected_missing_field"),
    [
        ("run_id", "proposed_action.run_id"),
        ("tenant_id", "proposed_action.tenant_id"),
    ],
)
@pytest.mark.asyncio
async def test_event_generator_rejects_spoofed_interrupt_proposed_action_identity(
    session: AsyncSession,
    seeded_session,
    spoof_field: str,
    expected_missing_field: str,
):
    user = seeded_session["users"]["cs_zhang"]
    run = await _create_run(session, tenant_id=user.tenant_id, user_id=user.id, final_status="running")
    await session.commit()
    spoof_run_id = uuid4()
    spoof_tenant_id = uuid4()
    graph = StreamInterruptGraph(
        proposed_action_run_id=str(spoof_run_id) if spoof_field == "run_id" else None,
        proposed_action_tenant_id=str(spoof_tenant_id) if spoof_field == "tenant_id" else None,
    )

    generator = _event_generator(
        graph,
        _stream_input(run, user),
        {"configurable": {"thread_id": run.thread_id, "session": session}},
        run=run,
        session=session,
        user=user,
    )

    events = [event async for event in generator]
    error_events = [
        _event_data(event)
        for event in events
        if "data" in event and _event_data(event).get("event_type") == "error"
    ]

    await session.refresh(run)
    assert len(error_events) == 1
    assert error_events[0]["payload"]["error_code"] == APPROVAL_NOT_EXECUTABLE
    assert error_events[0]["payload"]["missing_fields"] == [expected_missing_field]
    assert run.final_status == "error"
    assert await _count_rows(session, ApprovalRequest, ApprovalRequest.run_id == run.id) == 0
    assert await _count_rows(session, ApprovalRequest, ApprovalRequest.run_id == spoof_run_id) == 0


def test_agent_chat_only_support_token_receives_no_tool_permissions():
    """A support-role token with only agent:chat gets permissions=[] in trusted config."""
    from unittest.mock import MagicMock
    from src.api.routers.agent_runs import _trusted_tool_config

    user = MagicMock()
    user.role = "support"

    # The intersection of token_scopes={"agent:chat"} and ROLE_SCOPES["support"]
    # should yield no tool permissions since agent:chat has no tool mapping
    config = _trusted_tool_config(user, token_scopes=["agent:chat"], trace_id="test-trace")
    assert config["permissions"] == []


@pytest.mark.asyncio
async def test_agent_chat_only_token_streams_with_no_tool_permissions(
    client: AsyncClient,
    seeded_session,
    monkeypatch,
):
    user = seeded_session["users"]["cs_zhang"]
    graph = CaptureConfigGraph()
    monkeypatch.setattr(app.state, "agent_graph", graph, raising=False)
    create_response = await client.post(
        "/api/v1/agent-runs",
        json={"query": "权限最小化测试", "thread_id": f"restricted-stream-{uuid4()}"},
        headers=_auth_header(user, ["agent:chat"]),
    )
    assert create_response.status_code == 200
    run_id = create_response.json()["data"]["run_id"]

    response = await client.get(
        f"/api/v1/agent-runs/{run_id}/events",
        headers=_auth_header(user, ["agent:chat"]),
    )

    assert response.status_code == 200
    assert len(graph.calls) == 1
    _, config = graph.calls[0]
    assert config["configurable"]["permissions"] == []


@pytest.mark.asyncio
async def test_agent_chat_only_token_invokes_legacy_chat_with_no_tool_permissions(
    client: AsyncClient,
    session: AsyncSession,
    seeded_session,
    monkeypatch,
):
    user = seeded_session["users"]["cs_zhang"]
    graph = CaptureInvokeConfigGraph()
    monkeypatch.setattr(app.state, "agent_graph", graph, raising=False)
    thread_id = f"restricted-chat-{uuid4()}"

    response = await client.post(
        "/api/v1/agent/chat",
        json={"query": "退款政策是什么？", "thread_id": thread_id},
        headers=_auth_header(user, ["agent:chat"]),
    )

    assert response.status_code == 200
    assert response.json()["success"] is True
    assert response.json()["data"]["response"] == "done"
    assert len(graph.calls) == 1
    input_state, config = graph.calls[0]
    trusted_context = TrustedContext.model_validate(config["configurable"]["trusted_context"])
    legacy_identity = project_to_legacy_agent_state_identity(trusted_context)
    assert config["configurable"]["permissions"] == []
    assert input_state["current_run_id"] == legacy_identity["current_run_id"]
    assert config["configurable"]["permissions"] == trusted_context.permissions
    assert config["configurable"]["merchant_scope"] == trusted_context.merchant_scope.model_dump(mode="json")
    assert "conversation_thread_id" in config["configurable"]
    assert "conversation_message_id" in config["configurable"]

    messages = (
        (
            await session.execute(
                select(ConversationMessage)
                .where(
                    ConversationMessage.tenant_id == user.tenant_id,
                    ConversationMessage.thread_id == thread_id,
                    ConversationMessage.deleted_at.is_(None),
                )
                .order_by(ConversationMessage.message_index)
            )
        )
        .scalars()
        .all()
    )
    assert [message.role for message in messages] == ["user", "assistant"]
    assert messages[0].content == "退款政策是什么？"
    assert messages[1].content == "done"
    assert str(messages[0].conversation_thread_id) == config["configurable"]["conversation_thread_id"]
    assert str(messages[0].id) == config["configurable"]["conversation_message_id"]

    summaries = (
        (
            await session.execute(
                select(ConversationSummary).where(
                    ConversationSummary.tenant_id == user.tenant_id,
                    ConversationSummary.thread_id == thread_id,
                    ConversationSummary.summary_type == "thread_rolling",
                    ConversationSummary.deleted_at.is_(None),
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(summaries) == 1
    assert summaries[0].source_message_ids_json == [str(message.id) for message in messages]


@pytest.mark.asyncio
async def test_agent_chat_persists_trusted_run_id_when_graph_returns_stale_current_run_id(
    client: AsyncClient,
    session: AsyncSession,
    seeded_session,
    monkeypatch,
):
    user = seeded_session["users"]["cs_zhang"]
    spoof_run_id = uuid4()
    graph = SpoofRunIdInvokeGraph(str(spoof_run_id))
    monkeypatch.setattr(app.state, "agent_graph", graph, raising=False)

    response = await client.post(
        "/api/v1/agent/chat",
        json={"query": "退款政策是什么？", "thread_id": f"trusted-run-chat-{uuid4()}"},
        headers=_auth_header(user, ["agent:chat"]),
    )

    assert response.status_code == 200
    assert response.json()["success"] is True
    assert len(graph.calls) == 1
    input_state, config = graph.calls[0]
    trusted_context = TrustedContext.model_validate(config["configurable"]["trusted_context"])

    trusted_run = await session.get(AgentRun, UUID(trusted_context.run_id))
    spoof_run = await session.get(AgentRun, spoof_run_id)

    assert input_state["current_run_id"] == trusted_context.run_id
    assert response.json()["data"]["trace_summary"]["run_id"] == trusted_context.run_id
    assert trusted_run is not None
    assert trusted_run.final_status == "completed"
    assert spoof_run is None


@pytest.mark.parametrize("raise_interrupt", [False, True])
@pytest.mark.asyncio
async def test_agent_chat_interrupt_uses_trusted_run_id_when_payload_and_checkpoint_spoof(
    client: AsyncClient,
    session: AsyncSession,
    seeded_session,
    monkeypatch,
    raise_interrupt: bool,
):
    user = seeded_session["users"]["cs_zhang"]
    target_merchant_id = str(seeded_session["merchant"].id)
    spoof_payload_run_id = uuid4()
    spoof_checkpoint_run_id = uuid4()
    graph = SpoofInterruptInvokeGraph(
        interrupt_run_id=str(spoof_payload_run_id),
        checkpoint_run_id=str(spoof_checkpoint_run_id),
        target_merchant_id=target_merchant_id,
        raise_interrupt=raise_interrupt,
    )
    monkeypatch.setattr(app.state, "agent_graph", graph, raising=False)

    response = await client.post(
        "/api/v1/agent/chat",
        json={"query": "请补偿 600 元", "thread_id": f"trusted-interrupt-chat-{uuid4()}"},
        headers=_auth_header(user, ["agent:chat"]),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert len(graph.calls) == 1
    input_state, config = graph.calls[0]
    trusted_context = TrustedContext.model_validate(config["configurable"]["trusted_context"])
    trusted_run_id = UUID(trusted_context.run_id)

    trusted_run = await session.get(AgentRun, trusted_run_id)
    spoof_payload_run = await session.get(AgentRun, spoof_payload_run_id)
    spoof_checkpoint_run = await session.get(AgentRun, spoof_checkpoint_run_id)
    trusted_approval = (
        await session.execute(select(ApprovalRequest).where(ApprovalRequest.run_id == trusted_run_id))
    ).scalar_one()

    assert input_state["current_run_id"] == trusted_context.run_id
    assert body["data"]["run_id"] == trusted_context.run_id
    assert trusted_run is not None
    assert trusted_run.final_status == "interrupted"
    assert trusted_approval.run_id == trusted_run_id
    assert trusted_approval.proposed_action["run_id"] == trusted_context.run_id
    assert trusted_approval.target_merchant_id == target_merchant_id
    assert trusted_approval.business_fact_refs[0]["resource_id"] == "ORD-2024-001"
    assert trusted_approval.verified_evidence_refs[0]["doc_key"] == "refund_policy"
    assert trusted_approval.claim_verification_ref is None
    assert trusted_approval.risk_decision_ref == f"risk_decision:{trusted_run_id}:r1"
    assert trusted_approval.risk_decision["run_id"] == trusted_context.run_id
    assert trusted_approval.approval_idempotency_key == f"approval:{user.tenant_id}:{trusted_context.run_id}"
    assert spoof_payload_run is None
    assert spoof_checkpoint_run is None
    assert await _count_rows(session, ApprovalRequest, ApprovalRequest.run_id == spoof_payload_run_id) == 0
    assert await _count_rows(session, ApprovalRequest, ApprovalRequest.run_id == spoof_checkpoint_run_id) == 0


@pytest.mark.parametrize(
    ("spoof_field", "expected_missing_field"),
    [
        ("run_id", "proposed_action.run_id"),
        ("tenant_id", "proposed_action.tenant_id"),
    ],
)
@pytest.mark.asyncio
async def test_agent_chat_interrupt_rejects_proposed_action_identity_mismatch(
    client: AsyncClient,
    session: AsyncSession,
    seeded_session,
    monkeypatch,
    spoof_field: str,
    expected_missing_field: str,
):
    user = seeded_session["users"]["cs_zhang"]
    spoof_action_run_id = uuid4()
    spoof_action_tenant_id = uuid4()
    graph = SpoofInterruptInvokeGraph(
        proposed_action_run_id=str(spoof_action_run_id) if spoof_field == "run_id" else None,
        proposed_action_tenant_id=str(spoof_action_tenant_id) if spoof_field == "tenant_id" else None,
    )
    monkeypatch.setattr(app.state, "agent_graph", graph, raising=False)

    response = await client.post(
        "/api/v1/agent/chat",
        json={"query": "请补偿 600 元", "thread_id": f"trusted-action-chat-{uuid4()}"},
        headers=_auth_header(user, ["agent:chat"]),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == APPROVAL_NOT_EXECUTABLE
    assert body["error"]["details"]["missing_fields"] == [expected_missing_field]
    assert len(graph.calls) == 1
    _, config = graph.calls[0]
    trusted_context = TrustedContext.model_validate(config["configurable"]["trusted_context"])
    trusted_run_id = UUID(trusted_context.run_id)

    trusted_run = await session.get(AgentRun, trusted_run_id)
    spoof_action_run = await session.get(AgentRun, spoof_action_run_id)

    assert body["data"]["run_id"] == trusted_context.run_id
    assert trusted_run is not None
    assert trusted_run.final_status == "interrupted"
    assert spoof_action_run is None
    assert await _count_rows(session, ApprovalRequest, ApprovalRequest.run_id == trusted_run_id) == 0
    assert await _count_rows(session, ApprovalRequest, ApprovalRequest.run_id == spoof_action_run_id) == 0


@pytest.mark.asyncio
async def test_chat_memory_write_background_returns_final_response_before_slow_hook(
    client: AsyncClient,
    seeded_session,
    monkeypatch,
):
    user = seeded_session["users"]["cs_zhang"]
    graph = CaptureInvokeConfigGraph()
    monkeypatch.setattr(app.state, "agent_graph", graph, raising=False)
    started = asyncio.Event()
    finished = asyncio.Event()
    captured: dict[str, object] = {}

    def fake_schedule_memory_write(final_state, *, session_factory, trace_id=None):
        captured["session_factory"] = session_factory

        async def slow_hook():
            started.set()
            await asyncio.sleep(0.2)
            finished.set()

        return asyncio.create_task(slow_hook())

    monkeypatch.setattr("src.api.routers.agent._schedule_memory_write_after_response", fake_schedule_memory_write)

    response = await client.post(
        "/api/v1/agent/chat",
        json={"query": "退款政策是什么？", "thread_id": f"memory-write-chat-{uuid4()}"},
        headers=_auth_header(user, ["agent:chat"]),
    )

    assert response.status_code == 200
    assert response.json()["data"]["response"] == "done"
    assert captured["session_factory"] is not None
    assert started.is_set()
    assert not finished.is_set()


@pytest.mark.asyncio
async def test_sse_final_response_after_bounded_memory_persistence_result(
    session: AsyncSession, seeded_session, monkeypatch
):
    user = seeded_session["users"]["cs_zhang"]
    run = await _create_run(session, tenant_id=user.tenant_id, user_id=user.id, final_status="running")
    await session.commit()
    memory_results: list[dict] = []

    async def fake_memory_write(final_state, config):
        assert final_state["tenant_id"] == str(user.tenant_id)
        assert final_state["user_id"] == str(user.id)
        assert final_state["thread_id"] == run.thread_id
        assert final_state["current_run_id"] == str(run.id)
        assert final_state["final_response"] == "done"
        assert config["configurable"]["session"] is not session
        result = {"status": "completed", "reason_code": "memory_persisted"}
        memory_results.append(result)
        return {
            **final_state,
            "memory_write_result": result,
            "trace_steps": [
                {
                    "node": "memory_write",
                    "status": "completed",
                    "started_at": datetime.now(UTC).isoformat(),
                    "completed_at": datetime.now(UTC).isoformat(),
                }
            ],
        }

    monkeypatch.setattr("src.api.services.agent_run_memory.memory_write", fake_memory_write)
    generator = _event_generator(
        CaptureConfigGraph(),
        {"user_query": run.input_query},
        {"configurable": {"thread_id": run.thread_id, "session": session}},
        run=run,
        session=session,
        user=user,
    )

    final_event = None
    try:
        async for event in generator:
            if "data" in event and '"event_type": "final_response"' in event["data"]:
                final_event = event
                assert memory_results == [{"status": "completed", "reason_code": "memory_persisted"}]
                break
        assert final_event is not None
    finally:
        await generator.aclose()


@pytest.mark.asyncio
async def test_sse_lifecycle_events_final_response_after_bounded_memory_persistence_result(
    session: AsyncSession, seeded_session, monkeypatch
):
    user = seeded_session["users"]["cs_zhang"]
    run = await _create_run(session, tenant_id=user.tenant_id, user_id=user.id, final_status="running")
    await session.commit()
    graph = GatedLifecycleGraph()
    memory_results: list[dict] = []

    async def fake_memory_write(final_state, config):
        assert final_state["tenant_id"] == str(user.tenant_id)
        assert final_state["user_id"] == str(user.id)
        assert final_state["thread_id"] == run.thread_id
        assert final_state["current_run_id"] == str(run.id)
        assert final_state["final_response"] == "done"
        assert config["configurable"]["session"] is not session
        result = {"status": "completed", "reason_code": "memory_persisted"}
        memory_results.append(result)
        return {
            **final_state,
            "memory_write_result": result,
            "trace_steps": [
                {
                    "node": "memory_write",
                    "status": "completed",
                    "started_at": datetime.now(UTC).isoformat(),
                    "completed_at": datetime.now(UTC).isoformat(),
                }
            ],
        }

    monkeypatch.setattr("src.api.services.agent_run_memory.memory_write", fake_memory_write)
    generator = _event_generator(
        graph,
        {"user_query": run.input_query},
        {"configurable": {"thread_id": run.thread_id, "session": session}},
        run=run,
        session=session,
        user=user,
    )

    final_event = None
    try:
        async for event in generator:
            if "data" in event and '"event_type": "step_started"' in event["data"]:
                graph.allow_completion.set()
            if "data" in event and '"event_type": "final_response"' in event["data"]:
                final_event = event
                assert memory_results == [{"status": "completed", "reason_code": "memory_persisted"}]
                break
        assert final_event is not None
    finally:
        await generator.aclose()


@pytest.mark.asyncio
async def test_completed_agent_run_finalizer_skips_non_completed_status(
    session: AsyncSession,
    seeded_session,
):
    user = seeded_session["users"]["cs_zhang"]
    run = await _create_run(session, tenant_id=user.tenant_id, user_id=user.id, final_status="running")
    await session.flush()

    result = await finalize_completed_agent_run_memory(
        session=session,
        run=run,
        user=user,
        input_state=_stream_input(run, user),
        final_state={"final_response": "x"},
        final_status="error",
        final_response="x",
        trace_steps=[],
        trace_id=None,
    )

    assert result.status == "skipped"
    assert result.trace_steps == []
    assert await _count_rows(session, ConversationMessage, ConversationMessage.run_id == run.id, ConversationMessage.role == "assistant") == 0
    assert await _count_rows(session, ConversationSummary, ConversationSummary.thread_id == run.thread_id) == 0
    assert await _count_rows(session, MemoryWriteEvent, MemoryWriteEvent.run_id == run.id) == 0


@pytest.mark.asyncio
async def test_completed_agent_run_finalizer_memory_write_rollback_does_not_remove_terminal_rows(
    session: AsyncSession,
    seeded_session,
    monkeypatch,
):
    user = seeded_session["users"]["cs_zhang"]
    run = await _create_run(session, tenant_id=user.tenant_id, user_id=user.id, final_status="running")
    await session.commit()

    async def fake_memory_write(final_state, config):
        memory_session = config["configurable"]["session"]
        assert memory_session is not session
        await memory_session.rollback()
        return {
            **final_state,
            "memory_write_result": {
                "status": "fallback",
                "reason_code": "unavailable",
                "slot_count": 2,
                "fallback_reason": "repository_unavailable",
                "decision": "skip",
                "pii_classification": "none",
            },
            "trace_steps": [],
        }

    monkeypatch.setattr("src.api.services.agent_run_memory.memory_write", fake_memory_write)

    result = await finalize_completed_agent_run_memory(
        session=session,
        run=run,
        user=user,
        input_state=_stream_input(run, user),
        final_state={"final_response": "done"},
        final_status="completed",
        final_response="done",
        trace_steps=[],
        trace_id=None,
    )
    await session.commit()

    assert result.memory_write_status == "failed"
    metrics = result.trace_steps[0]["metrics_json"]
    assert metrics["memory_write_status"] == "failed"
    assert metrics["memory_write_reason_code"] == "unavailable"
    assert isinstance(metrics["memory_write_duration_ms"], int)
    assert metrics["slot_count"] == 2
    assert metrics["fallback_reason"] == "repository_unavailable"
    assert metrics["pii_decision"] == "skip"
    assert metrics["pii_classification"] == "none"
    assert await _count_rows(
        session,
        ConversationMessage,
        ConversationMessage.run_id == run.id,
        ConversationMessage.role == "assistant",
    ) == 1
    assert await _count_rows(session, ConversationSummary, ConversationSummary.thread_id == run.thread_id) == 1


@pytest.mark.asyncio
async def test_completed_agent_run_finalizer_rolls_back_if_complete_run_fails(
    session: AsyncSession,
    seeded_session,
    monkeypatch,
):
    user = seeded_session["users"]["cs_zhang"]
    run = await _create_run(session, tenant_id=user.tenant_id, user_id=user.id, final_status="running")
    await session.commit()

    class MemoryEligibleGraph:
        async def astream(self, input_state, config, stream_mode):
            yield (
                "final_response",
                {
                    "current_run_id": str(run.id),
                    "current_intent": "refund_troubleshooting",
                    "primary_intent": "refund_troubleshooting",
                    "extracted_slots": {"order_id": "ORD-COMPLETE-FAIL"},
                    "final_response": "done",
                    "trace_steps": [_trace("final_response")],
                },
            )

    async def fail_write_agent_steps(*args, **kwargs):
        raise RuntimeError("step write failed")

    monkeypatch.setattr("src.api.routers.agent_runs.write_agent_steps", fail_write_agent_steps)
    events = [
        event
        async for event in _event_generator(
            MemoryEligibleGraph(),
            _stream_input(run, user),
            {"configurable": {"thread_id": run.thread_id, "session": session}},
            run=run,
            session=session,
            user=user,
        )
    ]

    assert any('"event_type": "error"' in event.get("data", "") for event in events)
    assert await _count_rows(session, ConversationMessage, ConversationMessage.run_id == run.id, ConversationMessage.role == "assistant") == 0
    assert await _count_rows(session, ConversationSummary, ConversationSummary.thread_id == run.thread_id) == 0
    assert await _count_rows(session, MemoryWriteEvent, MemoryWriteEvent.run_id == run.id) == 0
    assert await _count_rows(session, SessionMemory, SessionMemory.thread_id == run.thread_id) == 0
    assert await _count_rows(session, AgentStep, AgentStep.run_id == run.id, AgentStep.node_name == "agent_run_memory_finalize") == 0
    await session.refresh(run)
    assert run.final_status == "error"


@pytest.mark.asyncio
async def test_sse_interrupted_path_skips_memory_write(session: AsyncSession, seeded_session, monkeypatch):
    user = seeded_session["users"]["cs_zhang"]
    run = await _create_run(session, tenant_id=user.tenant_id, user_id=user.id, final_status="running")
    await session.commit()
    scheduled: list[dict] = []

    def fake_schedule_memory_write(final_state, *, session_factory, trace_id=None):
        scheduled.append(final_state)

    monkeypatch.setattr("src.api.routers.agent_runs._schedule_memory_write_after_response", fake_schedule_memory_write)
    generator = _event_generator(
        StreamInterruptGraph(),
        _stream_input(run, user),
        {"configurable": {"thread_id": run.thread_id, "session": session}},
        run=run,
        session=session,
        user=user,
    )

    events = [event async for event in generator]

    assert any("approval_required" in event.get("data", "") for event in events)
    assert scheduled == []


@pytest.mark.asyncio
async def test_agent_run_error_cancel_interrupted_do_not_write_completed_memory(
    session: AsyncSession,
    seeded_session,
):
    user = seeded_session["users"]["cs_zhang"]

    error_run = await _create_run(session, tenant_id=user.tenant_id, user_id=user.id, final_status="running")
    cancelled_run = await _create_run(session, tenant_id=user.tenant_id, user_id=user.id, final_status="running")
    interrupted_run = await _create_run(session, tenant_id=user.tenant_id, user_id=user.id, final_status="running")
    await session.commit()

    error_events = [
        event
        async for event in _event_generator(
            ErrorGraph(),
            _stream_input(error_run, user),
            {"configurable": {"thread_id": error_run.thread_id, "session": session}},
            run=error_run,
            session=session,
            user=user,
        )
    ]
    with pytest.raises(asyncio.CancelledError):
        generator = _event_generator(
            CancelledGraph(),
            _stream_input(cancelled_run, user),
            {"configurable": {"thread_id": cancelled_run.thread_id, "session": session}},
            run=cancelled_run,
            session=session,
            user=user,
        )
        await anext(generator)
        await anext(generator)
    interrupted_events = [
        event
        async for event in _event_generator(
            StreamInterruptGraph(),
            _stream_input(interrupted_run, user),
            {"configurable": {"thread_id": interrupted_run.thread_id, "session": session}},
            run=interrupted_run,
            session=session,
            user=user,
        )
    ]

    assert any('"event_type": "error"' in event.get("data", "") for event in error_events)
    assert any('"event_type": "approval_required"' in event.get("data", "") for event in interrupted_events)
    for run in (error_run, cancelled_run, interrupted_run):
        await session.refresh(run)
        assert run.final_status in {"error", "interrupted"}
        assert await _count_rows(session, ConversationMessage, ConversationMessage.run_id == run.id, ConversationMessage.role == "assistant") == 0
        assert await _count_rows(session, ConversationSummary, ConversationSummary.thread_id == run.thread_id) == 0


@pytest.mark.asyncio
async def test_duplicate_sse_stream_does_not_duplicate_memory_surfaces(
    client: AsyncClient,
    session: AsyncSession,
    seeded_session,
    monkeypatch,
):
    from src.api.routers import agent_runs as agent_runs_router
    from src.api.services import agent_run_memory as agent_run_memory_service
    from src.conversation.service import ConversationService
    from src.memory.thread_summary import ThreadRollingSummaryService

    user = seeded_session["users"]["cs_zhang"]
    graph = CaptureConfigGraph()
    calls = {
        "assistant_message": 0,
        "finalizer": 0,
        "graph": 0,
        "memory_write": 0,
        "summary": 0,
        "user_message": 0,
    }
    original_user_message = ConversationService.append_or_get_user_message_for_run
    original_assistant_message = ConversationService.append_or_get_assistant_message_for_run
    original_summary = ThreadRollingSummaryService.persist_thread_summary
    original_finalizer = agent_runs_router.finalize_completed_agent_run_memory
    original_memory_write = agent_run_memory_service.memory_write

    async def spy_user_message(self, *args, **kwargs):
        calls["user_message"] += 1
        return await original_user_message(self, *args, **kwargs)

    async def spy_assistant_message(self, *args, **kwargs):
        calls["assistant_message"] += 1
        return await original_assistant_message(self, *args, **kwargs)

    async def spy_summary(self, *args, **kwargs):
        calls["summary"] += 1
        return await original_summary(self, *args, **kwargs)

    async def spy_finalizer(*args, **kwargs):
        calls["finalizer"] += 1
        return await original_finalizer(*args, **kwargs)

    async def spy_memory_write(*args, **kwargs):
        calls["memory_write"] += 1
        return await original_memory_write(*args, **kwargs)

    monkeypatch.setattr(ConversationService, "append_or_get_user_message_for_run", spy_user_message)
    monkeypatch.setattr(ConversationService, "append_or_get_assistant_message_for_run", spy_assistant_message)
    monkeypatch.setattr(ThreadRollingSummaryService, "persist_thread_summary", spy_summary)
    monkeypatch.setattr(agent_runs_router, "finalize_completed_agent_run_memory", spy_finalizer)
    monkeypatch.setattr(agent_run_memory_service, "memory_write", spy_memory_write)
    monkeypatch.setattr(app.state, "agent_graph", graph, raising=False)
    response = await client.post(
        "/api/v1/agent-runs",
        json={"query": "重复打开 SSE 不能重复写记忆", "thread_id": f"phase24-duplicate-{uuid4()}"},
        headers=_auth_header(user, ["agent:chat"]),
    )
    assert response.status_code == 200
    run_id = UUID(response.json()["data"]["run_id"])

    await _run_agent_run_stream(client, str(run_id), user)
    calls["graph"] = len(graph.calls)
    calls_after_first = dict(calls)
    counts_after_first = {
        "user": await _count_rows(session, ConversationMessage, ConversationMessage.run_id == run_id, ConversationMessage.role == "user"),
        "assistant": await _count_rows(
            session, ConversationMessage, ConversationMessage.run_id == run_id, ConversationMessage.role == "assistant"
        ),
        "tool_results": await _count_rows(session, ToolResultRecord, ToolResultRecord.run_id == run_id),
        "summaries": await _count_rows(session, ConversationSummary, ConversationSummary.thread_id.like("phase24-duplicate-%")),
        "session_memory_writes": await _count_rows(session, MemoryWriteEvent, MemoryWriteEvent.run_id == run_id),
    }
    duplicate_response = await client.get(
        f"/api/v1/agent-runs/{run_id}/events",
        headers=_auth_header(user, ["agent:chat"]),
    )
    assert duplicate_response.status_code == 409
    counts_after_duplicate = {
        "user": await _count_rows(session, ConversationMessage, ConversationMessage.run_id == run_id, ConversationMessage.role == "user"),
        "assistant": await _count_rows(
            session, ConversationMessage, ConversationMessage.run_id == run_id, ConversationMessage.role == "assistant"
        ),
        "tool_results": await _count_rows(session, ToolResultRecord, ToolResultRecord.run_id == run_id),
        "summaries": await _count_rows(session, ConversationSummary, ConversationSummary.thread_id.like("phase24-duplicate-%")),
        "session_memory_writes": await _count_rows(session, MemoryWriteEvent, MemoryWriteEvent.run_id == run_id),
    }

    assert calls_after_first == {
        "assistant_message": 1,
        "finalizer": 1,
        "graph": 1,
        "memory_write": 1,
        "summary": 1,
        "user_message": 1,
    }
    assert counts_after_first["user"] == 1
    assert counts_after_first["assistant"] == 1
    assert counts_after_first["tool_results"] == 0
    assert counts_after_first["summaries"] == 1
    assert counts_after_first["session_memory_writes"] >= 0
    assert counts_after_duplicate == counts_after_first
    calls["graph"] = len(graph.calls)
    assert calls == calls_after_first


@pytest.mark.asyncio
async def test_three_turn_agent_runs_smoke_uses_slots_and_summary_context(
    client: AsyncClient,
    session: AsyncSession,
    seeded_session,
    monkeypatch,
):
    user = seeded_session["users"]["cs_zhang"]
    graph = ThreeTurnMemoryGraph()
    monkeypatch.setattr(app.state, "agent_graph", graph, raising=False)
    thread_id = f"phase24-three-turn-{uuid4()}"

    run_ids: list[UUID] = []
    for query in (
        "订单 ORD-TEST-001 的退款 RF-TEST-001 进度如何？",
        "那这个订单下一步应该怎么处理？",
        "当前订单改查 ORD-TEST-999，总结一下刚才的问题和后续动作。",
    ):
        response = await client.post(
            "/api/v1/agent-runs",
            json={"query": query, "thread_id": thread_id},
            headers=_auth_header(user, ["agent:chat"]),
        )
        assert response.status_code == 200
        run_id = UUID(response.json()["data"]["run_id"])
        run_ids.append(run_id)
        await _run_agent_run_stream(client, str(run_id), user)

    assert await _count_rows(session, ConversationMessage, ConversationMessage.thread_id == thread_id, ConversationMessage.role == "user") >= 3
    assert await _count_rows(
        session,
        ConversationMessage,
        ConversationMessage.thread_id == thread_id,
        ConversationMessage.role == "assistant",
        ConversationMessage.metadata_json["status"].as_string() == "completed",
    ) >= 3
    assert await _count_rows(
        session,
        ConversationSummary,
        ConversationSummary.thread_id == thread_id,
        ConversationSummary.summary_type == "thread_rolling",
    ) >= 1
    assert await _count_rows(session, ToolResultRecord, ToolResultRecord.thread_id == thread_id) >= 3
    assert len(graph.calls) == 3
    assert len(graph.snapshots) == 3
    assert all("conversation_message_id" in config["configurable"] for _, config in graph.calls)
    assert all("conversation_thread_id" in config["configurable"] for _, config in graph.calls)
    assert set(run_ids) == {
        UUID(str(message.run_id))
        for message in (
            await session.execute(
                select(ConversationMessage).where(
                    ConversationMessage.thread_id == thread_id,
                    ConversationMessage.role == "user",
                )
            )
        )
        .scalars()
        .all()
    }
    turn1, turn2, turn3 = graph.snapshots
    assert turn1["active_slots"]["order_id"] == "ORD-TEST-001"
    assert turn1["active_slots"]["refund_case_id"] == "RF-TEST-001"
    assert turn2["session_memory"]["active_slots"]["order_id"] == "ORD-TEST-001"
    assert turn2["active_slots"]["order_id"] == "ORD-TEST-001"
    assert turn2["active_slot_metadata"]["order_id"]["source"] == "trusted_session_memory"
    assert "ORD-TEST-001" in turn2["prompt_summary"]
    assert any("Prompt-safe get_order summary for ORD-TEST-001" in summary for summary in turn2["tool_prompt_summaries"])
    assert any(role == "user" and "那这个订单下一步" in content for role, content in turn2["recent_messages"])
    assert turn3["session_memory"]["active_slots"]["order_id"] == "ORD-TEST-001"
    assert turn3["active_slots"]["order_id"] == "ORD-TEST-999"
    assert turn3["active_slot_metadata"]["order_id"]["source"] == "explicit_user"
    assert turn3["active_slot_metadata"]["order_id"]["previous_trusted_session_value"] == "ORD-TEST-001"
    assert "ORD-TEST-001" in turn3["prompt_summary"]
    assert any("Prompt-safe get_order summary" in summary for summary in turn3["tool_prompt_summaries"])
    serialized_configs = json.dumps([config["configurable"] for _, config in graph.calls], default=str)
    serialized_snapshots = json.dumps(graph.snapshots, ensure_ascii=False, default=str)
    serialized_memory_context = f"{serialized_configs}\n{serialized_snapshots}"
    assert "memory_policy_evidence_authority" not in serialized_memory_context
    assert "memory_business_fact_authority" not in serialized_memory_context
    assert "memory_action_authority" not in serialized_memory_context
    assert "memory_replay_truth" not in serialized_memory_context
    assert "approval_authority_body" not in serialized_memory_context
    assert "action_authority_body" not in serialized_memory_context
    assert all(snapshot["retrieved_evidence"]["evidence_refs"] for snapshot in graph.snapshots)
    assert all(snapshot["last_business_context_refs"]["business_fact_refs"] for snapshot in graph.snapshots)


def test_support_token_with_orders_read_gets_only_get_order():
    """A support token with agent:chat+orders:read gets exactly ['tool:get_order']."""
    from unittest.mock import MagicMock
    from src.api.routers.agent_runs import _trusted_tool_config

    user = MagicMock()
    user.role = "support"

    config = _trusted_tool_config(user, token_scopes=["agent:chat", "orders:read"], trace_id="test-trace")
    assert config["permissions"] == ["tool:get_order"]


def test_merchant_with_merchant_id_none_gets_empty_merchant_ids():
    """A merchant with merchant_id=None receives explicit deny-all scope."""
    from unittest.mock import MagicMock
    from src.api.routers.agent_runs import _trusted_tool_config

    user = MagicMock()
    user.role = "merchant"
    user.merchant_id = None

    config = _trusted_tool_config(user, token_scopes=["agent:chat"], trace_id="test-trace")

    assert config["merchant_scope"]["merchant_ids"] == []


def test_merchant_role_scopes_project_merchant_scope_and_tool_permissions():
    from unittest.mock import MagicMock
    from src.api.routers.agent_runs import _trusted_tool_config

    merchant_id = uuid4()
    user = MagicMock()
    user.role = "merchant"
    user.merchant_id = merchant_id

    config = _trusted_tool_config(user, token_scopes=ROLE_SCOPES["merchant"], trace_id="trace-merchant")

    assert config["merchant_scope"]["merchant_ids"] == [str(merchant_id)]
    assert "tool:get_order" in config["permissions"]
    assert config["trace_id"] == "trace-merchant"


def test_role_scopes_alone_widen_permissions():
    """Without token scope intersection, a support user would get all role permissions."""
    from unittest.mock import MagicMock
    from src.api.routers.agent_runs import _trusted_tool_config

    user = MagicMock()
    user.role = "support"
    user.merchant_id = "test-merchant"

    # Full role scopes should give all mapped permissions
    config = _trusted_tool_config(
        user,
        token_scopes=["orders:read", "refunds:read", "tickets:read", "knowledge:read", "agent:chat"],
        trace_id="test-trace",
    )
    assert set(config["permissions"]) == {
        "tool:get_order",
        "tool:get_refund_case",
        "tool:get_ticket",
        "tool:search_policy",
    }
