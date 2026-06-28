from __future__ import annotations

import json
import inspect
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest
from langgraph.checkpoint.memory import MemorySaver

from tests.agent.conftest import FakeLLM

from src.agent import trace as trace_module
from src.agent.graph import build_graph, route_after_approval, route_after_risk
from src.agent.graph_vocabulary import target_graph_name
from src.agent.nodes import assess_risk_and_approval as assess_risk_module
from src.agent.nodes import classify_intent as classify_intent_module
from src.agent.nodes import extract_slots as extract_slots_module
from src.agent.nodes import generate_recommendation as generate_recommendation_module
from src.agent.nodes import long_term_memory_retrieve as memory_retrieve_module
from src.agent.routing import (
    route_after_claim_verify,
    route_after_intent,
    route_after_investigate,
    route_after_rag_context,
    route_after_recommendation,
    route_after_slots,
)
from src.knowledge.config import RETRIEVAL_CONFIG_VERSION
from src.knowledge.schemas import (
    ClaimVerificationBundleV1,
    ClaimVerificationResultV1,
    EvidenceRefV1,
    MaterialClaimV1,
    VerifiedEvidencePackageV1,
)
from src.memory.schemas import SessionMemoryBundle, SessionMemoryView
from src.platform.trusted_context import MerchantScopeV1, TrustedContext
from src.tools.catalog import ToolCatalog
from src.tools.contracts import BusinessFactRefV1, ToolCallContext, ToolInvocationOutcome, ToolPolicyDecision, ToolResultV2, ToolViewV1
from src.tools.manager import UnifiedToolManager
from src.tools.projection import ToolResultProjector


INVESTIGATION_STATE_FIELDS = {
    "investigation_result",
    "investigation_steps",
    "investigation_trigger_reason",
    "investigation_path",
}
ROUTER_EDGE_KEYS = {
    "route_after_intent": {"clarification_gate", "final_response", "investigate", "session_memory_load"},
    "route_after_slots": {"clarification_gate", "investigate", "long_term_memory_retrieve"},
    "route_after_risk": {"approval_gate", "final_response"},
    "route_after_approval": {"assess_risk_and_approval", "action_draft", "final_response"},
    "route_after_investigate": {
        "final_response",
        "clarification_gate",
        "rag_context_build",
        "recommendation_generation",
    },
    "route_after_rag_context": {"recommendation_generation", "clarification_gate", "final_response"},
    "route_after_recommendation": {"claim_verify", "final_response"},
    "route_after_claim_verify": {"assess_risk_and_approval", "final_response"},
}
GRAPH_TEST_TENANT_ID = "11111111-1111-1111-1111-111111111111"
GRAPH_TEST_USER_ID = "22222222-2222-2222-2222-222222222222"


def _state(query: str, thread_id: str = "graph-test-thread") -> dict:
    return {
        "user_query": query,
        "thread_id": thread_id,
        "tenant_id": GRAPH_TEST_TENANT_ID,
        "user_id": GRAPH_TEST_USER_ID,
        "role": "support_agent",
    }


def _config(manager, events: list[dict[str, Any]], thread_id: str = "graph-test-thread", session: Any = None) -> dict:
    async def event_emitter(**payload):
        events.append(payload)

    permissions = [f"tool:{descriptor.name}" for descriptor in ToolCatalog().descriptors()]
    trusted_context = TrustedContext(
        tenant_id=GRAPH_TEST_TENANT_ID,
        user_id=GRAPH_TEST_USER_ID,
        role="support",
        permissions=permissions,
        merchant_scope=MerchantScopeV1(merchant_ids=["merchant-primary"]),
        session_id=None,
        thread_id=thread_id,
        run_id=str(uuid4()),
        trace_id="graph-trace",
        locale=None,
    )

    configurable = {
        "thread_id": thread_id,
        "session": session,
        "tool_manager": manager,
        "event_emitter": event_emitter,
        "trusted_context": trusted_context.model_dump(mode="json"),
        "policy_knowledge_service": FakeGraphPolicyKnowledgeService(),
        "permissions": permissions,
        "merchant_scope": {"merchant_ids": ["merchant-primary"]},
        "trace_id": "graph-trace",
    }
    if hasattr(manager, "_platform"):
        configurable["tool_platform"] = manager._platform
    return {"configurable": configurable}


def _intent(intent: str) -> dict:
    requested_operation = "advise" if intent == "policy_qa" else "read_status"
    required_slots = {"all_of": [], "any_of": [], "optional": []}
    if intent == "order_status_inquiry":
        required_slots = {"all_of": [], "any_of": [["order_id", "refund_case_id", "ticket_id"]], "optional": []}
    if intent == "refund_troubleshooting":
        required_slots = {"all_of": [], "any_of": [["order_id", "refund_case_id"]], "optional": []}
    return {
        "schema_version": "intent_result.v3",
        "primary_intent": intent,
        "requested_operation": requested_operation,
        "confidence": 0.95,
        "calibrated_confidence": 0.92,
        "secondary_intents": [],
        "required_slots": required_slots,
        "candidate_slots": {},
        "routing_hints": {},
        "classifier_version": "intent_classifier.v2",
        "calibration_version": "calibration.unverified",
        "reason_codes": ["test"],
    }


def _slots(order_id: str | None = None) -> dict:
    return {
        "order_id": order_id,
        "refund_case_id": None,
        "ticket_id": None,
        "merchant_id": None,
        "customer_id": None,
        "issue_type": "超时未退款" if order_id else None,
        "action_type": None,
    }


def _recommendation() -> dict:
    return {
        "recommended_action": "建议退款",
        "reasoning_summary": "退款超时时，客服应核实支付通道和退款状态。",
        "evidence_refs": [
            {
                "doc_key": "policy_refund_timeout",
                "chunk_id": "chunk_001",
                "title": "退款超时规则",
                "section": "第一条",
            }
        ],
        "confidence": 0.85,
        "risk_level": "low",
        "missing_info": [],
    }


def _risk() -> dict:
    return {"risk_level": "low", "risk_reason": "standard refund", "approval_required": False, "rule_ref": "LR-01"}


class FakeGraphToolManager:
    def __init__(self, *, order_id: str | None = None, policy_status: str = "strong_evidence") -> None:
        self._descriptors = {descriptor.name: descriptor for descriptor in ToolCatalog().descriptors()}
        self.order_id = order_id
        self.policy_status = policy_status
        self.calls: list[tuple[str, dict[str, Any], ToolCallContext]] = []
        self._platform = _FakeGraphToolPlatform(self)

    def descriptors(self, caller_node: str = "investigate"):
        return [
            descriptor
            for descriptor in self._descriptors.values()
            if caller_node in descriptor.caller_allowlist and descriptor.kind != "write"
        ]

    def descriptor(self, name: str):
        return self._descriptors.get(name)

    def event_family(self, name: str) -> str:
        family = self._descriptors[name].event_family
        return "rag_retrieval" if family == "rag_retrieval_*" else "tool_call"

    async def invoke(self, name: str, args: dict[str, Any], ctx: ToolCallContext) -> ToolResultV2:
        self.calls.append((name, args, ctx))
        if name == "get_order":
            return self._order_result(args.get("order_no") or self.order_id or "ORD-001")
        if name == "search_policy":
            return self._policy_result(ctx.tenant_id)
        raise AssertionError(f"Unexpected graph tool call: {name}")

    def _order_result(self, order_id: str) -> ToolResultV2:
        ref = BusinessFactRefV1(
            tenant_id=str(uuid4()),
            source_system="moca",
            resource_type="order",
            resource_id=order_id,
            resource_version=None,
            data_freshness_at=None,
            retrieved_at=datetime.now(UTC),
        )
        return ToolResultV2(
            status="success",
            data={"order_no": order_id, "status": "delivered", "amount": "199.00"},
            summary="order result",
            source_system="business_tool_service",
            data_freshness_at=None,
            policy_evidence_refs=[],
            business_fact_refs=[ref],
            error=None,
            retryable=False,
            retry_after_ms=None,
            latency_ms=1,
            audit_ref=None,
        )

    def _policy_result(self, tenant_id: str) -> ToolResultV2:
        evidence = []
        if self.policy_status != "no_evidence":
            evidence = [
                EvidenceRefV1.build(
                    tenant_id=tenant_id,
                    doc_key="policy_refund_timeout",
                    chunk_id="chunk_001",
                    policy_version="v1",
                    text="退款超时时，客服应核实支付通道和退款状态。",
                    retrieved_at="2026-06-07T02:30:00+00:00",
                    retrieval_config_version=RETRIEVAL_CONFIG_VERSION,
                    score=0.82,
                    rank=1,
                )
            ]
        return ToolResultV2(
            status="success" if evidence else "not_found",
            data={"retrieval_status": self.policy_status, "best_score": 0.82 if evidence else 0.0},
            summary="policy found" if evidence else "no policy found",
            source_system="policy_knowledge_service",
            data_freshness_at=None,
            policy_evidence_refs=evidence,
            business_fact_refs=[],
            error=None,
            retryable=False,
            retry_after_ms=None,
            latency_ms=1,
            audit_ref=None,
        )


class FakeGraphPolicyKnowledgeService:
    async def build_verified_context(
        self,
        *,
        candidate_evidence_refs: list[EvidenceRefV1],
        business_fact_refs: list[Any] | None,
        knowledge_context: Any,
        evidence_policy: dict[str, Any] | None = None,
    ) -> VerifiedEvidencePackageV1:
        if not candidate_evidence_refs:
            return VerifiedEvidencePackageV1(
                package_id=f"verified-evidence:{knowledge_context.run_id}:empty",
                status="no_evidence",
                evidence_items=[],
                citation_map={},
                evidence_map={},
                prompt_projection={},
                verifier_projection={"safe_refs": [], "business_fact_refs": []},
                replay_snapshot_refs=[],
                debug_projection={"reason_codes": ["candidate_evidence_required"]},
                stale_refs=[],
                conflict_refs=[],
                rejected_candidate_refs=[],
                reason_codes=["candidate_evidence_required"],
                policy_version="unknown",
                retrieval_config_version=RETRIEVAL_CONFIG_VERSION,
            )
        ref = candidate_evidence_refs[0]
        return VerifiedEvidencePackageV1(
            package_id=f"verified-evidence:{knowledge_context.run_id}:{ref.evidence_id}",
            status="verified",
            evidence_items=[],
            citation_map={"C1": [ref.evidence_id]},
            evidence_map={ref.evidence_id: ref},
            prompt_projection={"citations": [{"citation_id": "C1"}]},
            verifier_projection={
                "safe_refs": [ref.evidence_id],
                "business_fact_refs": business_fact_refs or [],
                "evidence_snippets": [
                    {
                        "citation_id": "C1",
                        "evidence_id": ref.evidence_id,
                        "text": "退款超时时，客服应核实支付通道和退款状态。",
                    }
                ],
            },
            replay_snapshot_refs=[ref.evidence_id],
            debug_projection={"reason_codes": []},
            stale_refs=[],
            conflict_refs=[],
            rejected_candidate_refs=[],
            reason_codes=[],
            policy_version=ref.policy_version,
            retrieval_config_version=ref.retrieval_config_version,
        )

    async def verify_claims(
        self,
        *,
        material_claims: list[MaterialClaimV1 | dict[str, Any]],
        verified_evidence_package: VerifiedEvidencePackageV1 | dict[str, Any] | None,
        business_context: dict[str, Any] | None,
        proposed_action: dict[str, Any] | None,
    ) -> ClaimVerificationBundleV1:
        package = VerifiedEvidencePackageV1.model_validate(verified_evidence_package)
        safe_refs = list(package.evidence_map.values())
        claim_results = [
            ClaimVerificationResultV1(
                claim_id=(claim.claim_id if isinstance(claim, MaterialClaimV1) else str(claim.get("claim_id"))),
                claim_type=(
                    claim.claim_type
                    if isinstance(claim, MaterialClaimV1)
                    else str(claim.get("claim_type") or "policy")
                ),
                support_status="supported",
                supporting_evidence_refs=safe_refs,
                business_fact_refs=[],
                rule_checks=[{"rule": "fake_graph_claim_verifier", "passed": True}],
                semantic_review_status="not_needed",
                allows_user_visible_claim=True,
                allows_action_recommendation=True,
            )
            for claim in material_claims
        ]
        return ClaimVerificationBundleV1(
            overall_status="verified",
            route="continue",
            claim_results=claim_results,
            blocked_claims=[],
            safe_support_refs=safe_refs,
            reason_codes=[],
            verifier_policy_version="material_claim_verifier.v1",
        )


class _FakeGraphToolPlatform:
    def __init__(self, manager: FakeGraphToolManager) -> None:
        self._manager = manager
        self._projector = ToolResultProjector()
        self.last_visibility_decisions = None

    async def visible_tools(
        self,
        *,
        caller: str,
        ctx: ToolCallContext,
        session: Any = None,
    ) -> list[ToolViewV1]:
        from src.tools.policy import ToolPolicyEngine, project_prompt_safe_input_schema

        engine = ToolPolicyEngine()
        decisions = engine.visibility_decisions(caller=caller, ctx=ctx)
        self.last_visibility_decisions = decisions
        views = []
        for decision in decisions:
            if decision.decision != "visible":
                continue
            descriptor = self._manager._descriptors.get(decision.tool_name)
            if descriptor is None:
                continue
            views.append(
                ToolViewV1(
                    name=descriptor.name,
                    description=descriptor.description,
                    input_schema=project_prompt_safe_input_schema(descriptor.input_schema),
                    safe_usage_notes=[],
                    result_contract_version="tool_result.v2",
                )
            )
        return views

    async def invoke(
        self,
        tool_name: str,
        args: dict[str, Any],
        ctx: ToolCallContext,
        *,
        session: Any = None,
    ) -> ToolInvocationOutcome:
        result = await self._manager.invoke(tool_name, args, ctx)
        projection = self._projector.project(
            tool_name=tool_name,
            result=result,
            tool_call_id=ctx.tool_call_id,
        )
        denied = result.status in {"permission_denied", "unavailable"}
        decision = ToolPolicyDecision(
            tool_name=tool_name,
            caller=ctx.caller_node,
            decision_stage="runtime_auth",
            decision="denied" if denied else "allowed",
            reason_codes=["missing_permission" if result.status == "permission_denied" else "tool_unavailable"]
            if denied
            else ["visible"],
            required_scopes=[],
            matched_scope=None,
            policy_version="tool_policy.v1",
            data_classification="internal",
            runtime_available=result.status != "unavailable",
        )
        return ToolInvocationOutcome(
            tool_result=result,
            projection=projection,
            policy_decision=decision,
            policy_event_id=None,
        )

    def descriptor(self, name: str):
        return self._manager._descriptors.get(name)

    def event_family(self, name: str) -> str | None:
        descriptor = self._manager._descriptors.get(name)
        if descriptor is None:
            return None
        if descriptor.event_family == "tool_call_*":
            return "tool_call"
        if descriptor.event_family == "rag_retrieval_*":
            return "rag_retrieval"
        if descriptor.event_family == "action":
            return "action"
        return None


def _patch_graph_dependencies(
    monkeypatch: pytest.MonkeyPatch,
    *,
    intent: str = "policy_qa",
    order_id: str | None = None,
    policy_status: str = "strong_evidence",
):
    monkeypatch.setattr(classify_intent_module, "_get_llm", lambda: FakeLLM(_intent(intent)))
    monkeypatch.setattr(extract_slots_module, "_get_llm", lambda: FakeLLM(_slots(order_id)))
    monkeypatch.setattr(generate_recommendation_module, "_get_llm", lambda: FakeLLM(_recommendation()))
    monkeypatch.setattr(assess_risk_module, "_get_llm", lambda: FakeLLM(_risk()))

    class FakePolicyKnowledgeService:
        def __init__(self, retriever) -> None:
            pass

        async def get_verified_evidence_contents(self, *, tenant_id, evidence_refs):
            return {
                ref.evidence_id: "退款超时时，客服应核实支付通道和退款状态。"
                for ref in evidence_refs
                if ref.tenant_id == tenant_id
            }

    monkeypatch.setattr(generate_recommendation_module, "PolicyKnowledgeService", FakePolicyKnowledgeService, raising=False)
    manager = FakeGraphToolManager(order_id=order_id, policy_status=policy_status)
    events: list[dict[str, Any]] = []
    return {"tool_manager": manager, "events": events}


def _session_memory_service(
    *,
    order_id: str = "ORD-SESSION-001",
    wrong_thread: bool = False,
    stale: bool = False,
):
    class FakeMemoryService:
        def __init__(self, repository, *, enabled: bool = True) -> None:
            pass

        async def load_session_memory(self, tenant_id, user_id, thread_id, current_intent):
            metadata = {
                "source": "trusted_session_memory",
                "tenant_id": tenant_id,
                "user_id": user_id,
                "thread_id": "wrong-thread" if wrong_thread else thread_id,
                "fresh": not stale,
                "expires_at": (
                    datetime.now(UTC) - timedelta(minutes=1) if stale else datetime.now(UTC) + timedelta(minutes=5)
                ).isoformat(),
                "compatible_intents": [current_intent],
            }
            return SessionMemoryView(
                source="postgres_session_memory",
                continuity_claimed=True,
                active_slots={"order_id": order_id},
                slot_metadata={"order_id": metadata},
                version=2,
            )

    return FakeMemoryService


def _session_memory_bundle_service(
    *,
    order_id: str = "ORD-SESSION-001",
    wrong_thread: bool = False,
    stale: bool = False,
):
    memory_service_type = _session_memory_service(order_id=order_id, wrong_thread=wrong_thread, stale=stale)

    class FakeBundleService:
        def __init__(self, *, conversation_service, memory_service) -> None:
            pass

        async def load_session_memory_bundle(self, **kwargs):
            view = await memory_service_type(None).load_session_memory(
                kwargs["tenant_id"],
                kwargs["user_id"],
                kwargs["thread_id"],
                kwargs.get("current_intent"),
            )
            return SessionMemoryBundle(
                tenant_id=str(kwargs["tenant_id"]),
                user_id=str(kwargs["user_id"]),
                thread_id=kwargs["thread_id"],
                run_id=str(kwargs["run_id"]),
                slot_continuity=view,
            )

    return FakeBundleService


class _FakeSession:
    async def execute(self, *args, **kwargs):
        raise AssertionError("fake bundle service should avoid repository reads")


def _patch_reviewed_memory_services(
    monkeypatch: pytest.MonkeyPatch,
    *,
    profile_items: list[dict[str, Any]] | None = None,
    case_items: list[dict[str, Any]] | None = None,
    fail: bool = False,
) -> None:
    class FakeLongTermMemoryService:
        def __init__(self, repository) -> None:
            pass

        async def retrieve_profile_memory(self, **kwargs):
            if fail:
                raise RuntimeError("reviewed long-term memory unavailable")
            return profile_items or []

    class FakeCaseMemoryService:
        def __init__(self, repository) -> None:
            pass

        async def retrieve_reviewed(self, request):
            if fail:
                raise RuntimeError("reviewed case memory unavailable")
            items = case_items or []
            return SimpleNamespace(status="success" if items else "empty", items=items)

    monkeypatch.setattr(memory_retrieve_module, "LongTermMemoryRepository", lambda session: object(), raising=False)
    monkeypatch.setattr(memory_retrieve_module, "CaseMemoryRepository", lambda session: object(), raising=False)
    monkeypatch.setattr(memory_retrieve_module, "LongTermMemoryService", FakeLongTermMemoryService, raising=False)
    monkeypatch.setattr(memory_retrieve_module, "CaseMemoryService", FakeCaseMemoryService, raising=False)


@pytest.mark.asyncio
async def test_happy_path_policy_qa_uses_investigate_manager(monkeypatch):
    deps = _patch_graph_dependencies(monkeypatch, intent="policy_qa")
    graph = build_graph(MemorySaver())

    final_state = await graph.ainvoke(
        _state("退款超时规则是什么？"),
        _config(deps["tool_manager"], deps["events"], session=object()),
    )

    assert final_state["final_response"]
    assert final_state["current_intent"] == "policy_qa"
    assert final_state["recommendation_draft"]["evidence_refs"]
    nodes = [step["node"] for step in final_state["trace_steps"]]
    assert final_state["risk_assessment"] is None
    assert "session_memory_load" not in nodes
    assert "investigate" in nodes
    assert "claim_verify" in nodes
    assert all(final_state[field] is None for field in INVESTIGATION_STATE_FIELDS)
    assert [call[0] for call in deps["tool_manager"].calls] == ["search_policy"]
    assert [event["event_type"] for event in deps["events"]] == ["rag_retrieval_started", "rag_retrieval_completed"]


@pytest.mark.asyncio
async def test_refund_path_preserves_business_context_facts(monkeypatch):
    deps = _patch_graph_dependencies(monkeypatch, intent="refund_troubleshooting", order_id="ORD-001")
    graph = build_graph(MemorySaver())

    final_state = await graph.ainvoke(
        _state("订单ORD-001退款为什么没到账？"),
        _config(deps["tool_manager"], deps["events"]),
    )

    assert final_state["current_intent"] == "refund_troubleshooting"
    assert final_state["business_context"]["facts"]["order"]["order_no"] == "ORD-001"
    assert [call[0] for call in deps["tool_manager"].calls] == ["get_order", "search_policy"]
    assert final_state["final_response"]


@pytest.mark.asyncio
async def test_refund_path_without_case_identifier_routes_to_clarification(monkeypatch):
    deps = _patch_graph_dependencies(monkeypatch, intent="refund_troubleshooting", order_id=None)
    graph = build_graph(MemorySaver())

    final_state = await graph.ainvoke(
        _state("退款为什么没到账？"),
        _config(deps["tool_manager"], deps["events"]),
    )

    assert deps["tool_manager"].calls == []
    assert final_state["clarification_request"]["reason"] == "missing_required_slots"
    assert "investigate" in final_state["clarification_request"]["blocked_nodes"]
    assert final_state["recommendation_draft"] is None
    assert final_state["final_response"] == "请提供订单号或退款单号。"
    assert final_state["llm_outputs"]["final_response"]["final_status"] == "insufficient_evidence"


@pytest.mark.asyncio
async def test_same_thread_session_memory_active_slots_feed_investigate(monkeypatch):
    deps = _patch_graph_dependencies(monkeypatch, intent="refund_troubleshooting", order_id=None)
    from src.agent.nodes import session_memory_load as session_memory_load_module

    monkeypatch.setattr(session_memory_load_module, "SessionMemoryBundleService", _session_memory_bundle_service())
    graph = build_graph(MemorySaver())

    final_state = await graph.ainvoke(
        _state("那这个退款呢？"),
        _config(deps["tool_manager"], deps["events"], session=_FakeSession()),
    )

    assert final_state["active_slots"]["order_id"] == "ORD-SESSION-001"
    assert final_state["active_slot_metadata"]["order_id"]["source"] == "trusted_session_memory"
    assert final_state["active_slot_metadata"]["order_id"]["explicit_current_turn"] is False
    assert final_state["extracted_slots"]["order_id"] is None
    assert final_state["business_context"]["facts"]["order"]["order_no"] == "ORD-SESSION-001"
    assert "session_memory_load" in [step["node"] for step in final_state["trace_steps"]]
    assert [call[0] for call in deps["tool_manager"].calls] == ["get_order", "search_policy"]
    assert deps["tool_manager"].calls[0][1]["order_no"] == "ORD-SESSION-001"
    assert final_state["final_response"]


@pytest.mark.asyncio
@pytest.mark.parametrize("memory_kwargs", [{"wrong_thread": True}, {"stale": True}])
async def test_wrong_thread_or_stale_session_memory_routes_to_clarification(monkeypatch, memory_kwargs):
    deps = _patch_graph_dependencies(monkeypatch, intent="refund_troubleshooting", order_id=None)
    from src.agent.nodes import session_memory_load as session_memory_load_module

    monkeypatch.setattr(
        session_memory_load_module,
        "SessionMemoryBundleService",
        _session_memory_bundle_service(**memory_kwargs),
    )
    graph = build_graph(MemorySaver())

    final_state = await graph.ainvoke(
        _state("那这个退款呢？"),
        _config(deps["tool_manager"], deps["events"], session=_FakeSession()),
    )

    assert deps["tool_manager"].calls == []
    assert final_state["clarification_request"]["reason"] == "missing_required_slots"
    assert final_state["active_slots"] == {}
    assert final_state["extracted_slots"]["order_id"] is None
    assert final_state["final_response"] == "请提供订单号或退款单号。"


@pytest.mark.asyncio
async def test_policy_qa_no_evidence_returns_insufficient_response(monkeypatch):
    deps = _patch_graph_dependencies(monkeypatch, intent="policy_qa", policy_status="no_evidence")
    graph = build_graph(MemorySaver())

    final_state = await graph.ainvoke(
        _state("退款超时规则是什么？"),
        _config(deps["tool_manager"], deps["events"]),
    )

    assert [call[0] for call in deps["tool_manager"].calls] == ["search_policy"]
    assert final_state["recommendation_draft"]["recommended_action"] == "insufficient_evidence"
    assert "没有找到足够证据" in final_state["final_response"]
    assert final_state["llm_outputs"]["final_response"]["final_status"] == "insufficient_evidence"


@pytest.mark.asyncio
async def test_policy_qa_direct_investigate_ignores_stale_active_slots(monkeypatch):
    deps = _patch_graph_dependencies(monkeypatch, intent="policy_qa")
    graph = build_graph(MemorySaver())

    final_state = await graph.ainvoke(
        _state("退款超时规则是什么？") | {"active_slots": {"order_id": "ORD-STALE"}},
        _config(deps["tool_manager"], deps["events"]),
    )

    assert [call[0] for call in deps["tool_manager"].calls] == ["search_policy"]
    assert "ORD-STALE" not in str(final_state["business_context"])


@pytest.mark.asyncio
async def test_order_status_inquiry_fact_only_path_renders_business_fact_response(monkeypatch):
    deps = _patch_graph_dependencies(monkeypatch, intent="order_status_inquiry", order_id="ORD-001")
    graph = build_graph(MemorySaver())

    final_state = await graph.ainvoke(
        _state("订单ORD-001的退款进度如何？"),
        _config(deps["tool_manager"], deps["events"]),
    )

    nodes = [step["node"] for step in final_state["trace_steps"]]
    assert final_state["current_intent"] == "order_status_inquiry"
    assert "generate_recommendation" not in nodes
    assert "已查询到订单信息" in final_state["final_response"]
    assert "ORD-001" in final_state["final_response"]
    assert "建议按已检索到的政策依据处理" not in final_state["final_response"]
    assert final_state["llm_outputs"]["final_response"]["final_status"] == "completed"
    assert [call[0] for call in deps["tool_manager"].calls] == ["get_order", "search_policy"]


@pytest.mark.asyncio
async def test_cross_turn_context_isolation_on_investigate_facts(monkeypatch):
    graph = build_graph(MemorySaver())
    thread_id = "cross-turn-thread"

    first = _patch_graph_dependencies(monkeypatch, intent="refund_troubleshooting", order_id="ORD-001")
    await graph.ainvoke(
        _state("订单ORD-001退款为什么没到账？", thread_id),
        _config(first["tool_manager"], first["events"], thread_id),
    )

    second = _patch_graph_dependencies(monkeypatch, intent="refund_troubleshooting", order_id="ORD-002")
    second_state = await graph.ainvoke(
        _state("订单ORD-002退款为什么没到账？", thread_id),
        _config(second["tool_manager"], second["events"], thread_id),
    )

    assert second_state["business_context"]["facts"]["order"]["order_no"] == "ORD-002"
    assert "ORD-001" not in str(second_state["business_context"])
    assert "ORD-001" not in str(second_state["trace_steps"])


@pytest.mark.asyncio
async def test_same_thread_stale_investigation_state_is_reset_on_next_turn(monkeypatch):
    deps = _patch_graph_dependencies(monkeypatch, intent="refund_troubleshooting", order_id="ORD-001")
    graph = build_graph(MemorySaver())
    thread_id = "stale-investigation-thread"
    stale_state = _state("订单ORD-001退款为什么没到账？", thread_id) | {
        "investigation_result": {"facts": ["stale"]},
        "investigation_steps": [{"tool": "search_policy"}],
        "investigation_trigger_reason": "stale_reason",
        "investigation_path": "investigation",
    }

    await graph.ainvoke(stale_state, _config(deps["tool_manager"], deps["events"], thread_id))

    next_deps = _patch_graph_dependencies(monkeypatch, intent="policy_qa")
    final_state = await graph.ainvoke(
        _state("退款超时规则是什么？", thread_id),
        _config(next_deps["tool_manager"], next_deps["events"], thread_id),
    )

    assert final_state["investigation_result"] is None
    assert final_state["investigation_steps"] is None
    assert final_state["investigation_trigger_reason"] is None
    assert final_state["investigation_path"] is None


@pytest.mark.asyncio
async def test_trace_summary_shape_uses_merged_investigate_tool_name(monkeypatch):
    deps = _patch_graph_dependencies(monkeypatch, intent="policy_qa")
    graph = build_graph(MemorySaver())
    final_state = await graph.ainvoke(_state("退款超时规则是什么？"), _config(deps["tool_manager"], deps["events"]))

    summary = trace_module.build_trace_summary(final_state["current_run_id"], final_state, 1000)

    assert set(summary) == {
        "run_id",
        "intent",
        "nodes_executed",
        "target_nodes_executed",
        "graph_projection",
        "target_merchant_context",
        "tools_called",
        "evidence_count",
        "risk_level",
        "total_latency_ms",
        "final_status",
        "rag_claim_summary",
    }
    assert "investigate" in summary["nodes_executed"]
    assert "investigate" in summary["target_nodes_executed"]
    assert summary["graph_projection"]["schema_version"] == "target_graph_projection.v1"
    assert summary["target_merchant_context"]["schema_version"] == "target_merchant_context.v1"
    assert summary["tools_called"] == ["search_policy"]
    assert summary["evidence_count"] == 1
    assert summary["final_status"] in ("completed", "insufficient_evidence", "error")
    assert summary["rag_claim_summary"]["schema_version"] == "rag_claim_summary.v1"
    assert INVESTIGATION_STATE_FIELDS.isdisjoint(summary)


def test_graph_compiles_with_investigate():
    graph = build_graph(MemorySaver())
    nodes = set(graph.get_graph().nodes)

    assert {
        "classify_intent",
        "investigate",
        "rag_context_build",
        "claim_verify",
        "clarification_gate",
        "session_memory_load",
        "long_term_memory_retrieve",
    } <= nodes
    assert "action_draft" in nodes
    assert "execute_action" not in nodes
    assert "load_business_context" not in nodes
    assert "retrieve_policy_evidence" not in nodes


def test_legacy_graph_runtime_names_project_to_target_vocabulary():
    graph = build_graph(MemorySaver())
    nodes = set(graph.get_graph().nodes)

    legacy_node_targets = {
        "classify_intent": "contextual_intent_resolve",
        "session_memory_load": "session_context_load",
        "extract_slots": "slot_resolution_gate",
        "long_term_memory_retrieve": "memory_context_load",
    }
    for legacy_node, target_node in legacy_node_targets.items():
        assert legacy_node in nodes
        assert target_graph_name(legacy_node, kind="node") == target_node

    legacy_router_targets = {
        "route_after_intent": "route_after_contextual_intent",
        "route_after_slots": "route_after_slot_resolution",
    }
    for legacy_router, target_router in legacy_router_targets.items():
        assert legacy_router in ROUTER_EDGE_KEYS
        assert target_graph_name(legacy_router, kind="router") == target_router


def test_phase_33_claim_verify_is_registered_as_runnable_graph_node():
    graph = build_graph(MemorySaver())
    nodes = set(graph.get_graph().nodes)
    conditional_edges = {(edge.source, edge.target) for edge in graph.get_graph().edges if edge.conditional}

    assert "rag_context_build" in nodes
    assert "claim_verify" in nodes
    assert ("generate_recommendation", "claim_verify") in conditional_edges
    assert ("claim_verify", "assess_risk_and_approval") in conditional_edges
    assert ("claim_verify", "final_response") in conditional_edges

    source = inspect.getsource(build_graph)
    assert 'builder.add_node("rag_context_build"' in source
    assert 'builder.add_node("claim_verify"' in source
    assert "route_after_claim_verify" in source


def test_approval_gate_edit_branch_is_registered_in_compiled_graph():
    graph = build_graph(MemorySaver()).get_graph()
    conditional_edges = {(edge.source, edge.target) for edge in graph.edges if edge.conditional}

    assert ("approval_gate", "assess_risk_and_approval") in conditional_edges
    assert ("approval_gate", "action_draft") in conditional_edges


def test_route_after_investigate_keys_are_edge_targets():
    graph = build_graph(MemorySaver())
    nodes = set(graph.get_graph().nodes)
    states = [
        {},
        {"business_context": {"missing_required_facts": ["order_id"]}},
        {"retrieval_status": "strong_evidence", "best_score": 0.9},
    ]
    mapping = {
        "final_response": "final_response",
        "clarification_gate": "clarification_gate",
        "rag_context_build": "rag_context_build",
        "recommendation_generation": "generate_recommendation",
    }

    for state in states:
        key = route_after_investigate(state)
        assert key in mapping
        assert mapping[key] in nodes


def test_all_router_return_keys_have_edges():
    assert (
        route_after_intent({"primary_intent": "policy_qa", "requested_operation": "advise", "intent_confidence": 0.9})
        in ROUTER_EDGE_KEYS["route_after_intent"]
    )
    assert (
        route_after_slots(
            {"primary_intent": "policy_qa", "required_slots": {"all_of": [], "any_of": [], "optional": []}}
        )
        in ROUTER_EDGE_KEYS["route_after_slots"]
    )
    assert ROUTER_EDGE_KEYS["route_after_slots"] == {"clarification_gate", "investigate", "long_term_memory_retrieve"}
    assert target_graph_name("route_after_slots", kind="router") == "route_after_slot_resolution"
    assert route_after_risk({"risk_assessment": {"approval_required": True}}) in ROUTER_EDGE_KEYS["route_after_risk"]
    assert (
        route_after_risk({"proposed_action": {"action_type": "issue_coupon"}}) in ROUTER_EDGE_KEYS["route_after_risk"]
    )
    assert route_after_risk({}) in ROUTER_EDGE_KEYS["route_after_risk"]
    assert (
        route_after_approval({"approval_result": {"decision": "approve"}}) in ROUTER_EDGE_KEYS["route_after_approval"]
    )
    assert route_after_approval({}) in ROUTER_EDGE_KEYS["route_after_approval"]
    assert route_after_investigate({}) in ROUTER_EDGE_KEYS["route_after_investigate"]
    assert (
        route_after_investigate({"business_context": {"missing_required_facts": ["order_id"]}})
        in ROUTER_EDGE_KEYS["route_after_investigate"]
    )
    assert (
        route_after_investigate({"retrieval_status": "strong_evidence", "best_score": 0.9})
        in ROUTER_EDGE_KEYS["route_after_investigate"]
    )
    assert route_after_rag_context({"rag_context_status": "verified"}) in ROUTER_EDGE_KEYS["route_after_rag_context"]
    assert route_after_rag_context({"rag_context_status": "build_error"}) in ROUTER_EDGE_KEYS["route_after_rag_context"]
    assert (
        route_after_recommendation({"material_claims": [{"claim_id": "claim-policy"}]})
        in ROUTER_EDGE_KEYS["route_after_recommendation"]
    )
    assert route_after_recommendation({}) in ROUTER_EDGE_KEYS["route_after_recommendation"]
    assert (
        route_after_claim_verify(
            {
                "claim_verification_bundle": {"overall_status": "verified", "route": "continue"},
                "proposed_action": {"type": "create_compensation_review"},
            }
        )
        in ROUTER_EDGE_KEYS["route_after_claim_verify"]
    )
    assert route_after_claim_verify({}) in ROUTER_EDGE_KEYS["route_after_claim_verify"]


def test_requested_operation_execute_action_remains_intent_taxonomy_value():
    payload = _intent("compensation_suggestion")
    payload["requested_operation"] = "execute_action"

    assert payload["requested_operation"] == "execute_action"


def test_post_merge_graph_uses_tool_manager_seam():
    assert UnifiedToolManager is not None


@pytest.mark.asyncio
async def test_approval_chat_routes_to_clarification_without_tools(monkeypatch):
    deps = _patch_graph_dependencies(monkeypatch, intent="policy_qa")
    graph = build_graph(MemorySaver())

    final_state = await graph.ainvoke(_state("approve APR-1"), _config(deps["tool_manager"], deps["events"]))

    assert deps["tool_manager"].calls == []
    assert final_state["clarification_request"]["reason"] == "approval_chat_not_trusted"
    assert "审批操作需要通过审批入口处理" in final_state["final_response"]


@pytest.mark.asyncio
async def test_long_term_memory_reviewed_retrieval_safe_empty_when_no_reviewed_rows(monkeypatch):
    payload = _intent("refund_troubleshooting")
    payload["routing_hints"] = {"needs_long_term_memory": True}
    monkeypatch.setattr(classify_intent_module, "_get_llm", lambda: FakeLLM(payload))
    monkeypatch.setattr(extract_slots_module, "_get_llm", lambda: FakeLLM(_slots("ORD-001")))
    monkeypatch.setattr(generate_recommendation_module, "_get_llm", lambda: FakeLLM(_recommendation()))
    monkeypatch.setattr(assess_risk_module, "_get_llm", lambda: FakeLLM(_risk()))
    _patch_reviewed_memory_services(monkeypatch, profile_items=[], case_items=[])
    manager = FakeGraphToolManager(order_id="ORD-001")
    events: list[dict[str, Any]] = []
    graph = build_graph(MemorySaver())

    final_state = await graph.ainvoke(
        _state("订单ORD-001退款为什么没到账？"),
        _config(manager, events, session=object()),
    )

    assert final_state["long_term_memory"] == []
    assert final_state["case_memory"] == []
    assert final_state["llm_outputs"]["long_term_memory_retrieve"]["source"] == "no_reviewed_memory"
    assert final_state["llm_outputs"]["long_term_memory_retrieve"]["continuity_claimed"] is False


@pytest.mark.asyncio
async def test_long_term_memory_retrieve_skips_case_memory_without_query() -> None:
    case_called = False

    class FakeLongTermMemoryService:
        async def retrieve_profile_memory(self, **kwargs):
            return []

    class FakeCaseMemoryService:
        async def retrieve_reviewed(self, request):
            nonlocal case_called
            case_called = True
            return SimpleNamespace(status="success", items=[{"case_memory_id": "case-1", "excerpt": "must not load"}])

    result = await memory_retrieve_module.long_term_memory_retrieve(
        {"tenant_id": str(uuid4()), "thread_id": "no-query-memory"},
        {
            "configurable": {
                "long_term_memory_service": FakeLongTermMemoryService(),
                "case_memory_service": FakeCaseMemoryService(),
            }
        },
    )

    assert case_called is False
    assert result["case_memory"] == []
    assert result["llm_outputs"]["long_term_memory_retrieve"]["source"] == "no_reviewed_memory"


@pytest.mark.asyncio
async def test_long_term_memory_reviewed_retrieval_safe_empty_when_unavailable(monkeypatch):
    payload = _intent("refund_troubleshooting")
    payload["routing_hints"] = {"needs_long_term_memory": True}
    monkeypatch.setattr(classify_intent_module, "_get_llm", lambda: FakeLLM(payload))
    monkeypatch.setattr(extract_slots_module, "_get_llm", lambda: FakeLLM(_slots("ORD-001")))
    monkeypatch.setattr(generate_recommendation_module, "_get_llm", lambda: FakeLLM(_recommendation()))
    monkeypatch.setattr(assess_risk_module, "_get_llm", lambda: FakeLLM(_risk()))
    _patch_reviewed_memory_services(monkeypatch, fail=True)
    manager = FakeGraphToolManager(order_id="ORD-001")
    events: list[dict[str, Any]] = []
    graph = build_graph(MemorySaver())

    final_state = await graph.ainvoke(
        _state("订单ORD-001退款为什么没到账？"),
        _config(manager, events, session=object()),
    )

    assert final_state["long_term_memory"] == []
    assert final_state["case_memory"] == []
    assert final_state["llm_outputs"]["long_term_memory_retrieve"]["source"] == "reviewed_memory_unavailable"
    assert final_state["llm_outputs"]["long_term_memory_retrieve"]["continuity_claimed"] is False


@pytest.mark.asyncio
async def test_long_term_memory_reviewed_snippets_flow_into_graph_state(monkeypatch):
    payload = _intent("refund_troubleshooting")
    payload["routing_hints"] = {"needs_long_term_memory": True}
    monkeypatch.setattr(classify_intent_module, "_get_llm", lambda: FakeLLM(payload))
    monkeypatch.setattr(extract_slots_module, "_get_llm", lambda: FakeLLM(_slots("ORD-001")))
    monkeypatch.setattr(generate_recommendation_module, "_get_llm", lambda: FakeLLM(_recommendation()))
    monkeypatch.setattr(assess_risk_module, "_get_llm", lambda: FakeLLM(_risk()))
    _patch_reviewed_memory_services(
        monkeypatch,
        profile_items=[
            {
                "memory_id": "profile-memory-1",
                "memory_kind": "preference",
                "content": "商家偏好先核实支付通道再给补偿建议。",
                "source_ref": {"conversation_id": "conv-1"},
                "EvidenceRefV1": {"evidence_id": "must-not-leak"},
                "approval_authority_body": {"approved": True},
                "raw_tool_payload": {"secret": "must-not-leak"},
            }
        ],
        case_items=[
            {
                "case_memory_id": "case-memory-1",
                "excerpt": "相似退款延迟案例先核实支付通道。",
                "applicability": "同类退款延迟",
                "outcome": "建议解释并跟进",
                "source_refs": [{"business_object_id": "refund-case-1"}],
                "policy_refs": [{"doc_key": "policy_refund_timeout", "chunk_id": "chunk_001"}],
                "action_authority_body": {"action": "issue_coupon"},
                "replay_debug_blob": {"raw": "must-not-leak"},
            }
        ],
    )
    manager = FakeGraphToolManager(order_id="ORD-001")
    events: list[dict[str, Any]] = []
    graph = build_graph(MemorySaver())

    final_state = await graph.ainvoke(
        _state("订单ORD-001退款为什么没到账？"),
        _config(manager, events, session=object()),
    )

    assert final_state["long_term_memory"][0]["memory_id"] == "profile-memory-1"
    assert final_state["long_term_memory"][0]["content"] == "商家偏好先核实支付通道再给补偿建议。"
    assert final_state["case_memory"][0]["case_memory_id"] == "case-memory-1"
    assert final_state["case_memory"][0]["excerpt"] == "相似退款延迟案例先核实支付通道。"
    assert final_state["llm_outputs"]["long_term_memory_retrieve"]["source"] == "reviewed_memory"
    assert final_state["llm_outputs"]["long_term_memory_retrieve"]["continuity_claimed"] is True
    state_json = json.dumps(
        {"long_term_memory": final_state["long_term_memory"], "case_memory": final_state["case_memory"]},
        ensure_ascii=False,
    )
    forbidden_terms = [
        "EvidenceRefV1",
        "approval_authority_body",
        "action_authority_body",
        "raw_tool_payload",
        "replay_debug_blob",
        "must-not-leak",
    ]
    assert all(term not in state_json for term in forbidden_terms)
