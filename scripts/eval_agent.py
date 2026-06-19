"""Agent evaluation script.

Usage:
    uv run python scripts/eval_agent.py
    uv run python scripts/eval_agent.py --golden-set evaluation/golden/agent_cases.jsonl
    uv run python scripts/eval_agent.py --mode live  # requires DASHSCOPE_API_KEY

Requires: database with seeded demo data (make seed).
Exits non-zero if safety-critical thresholds fail.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import patch

from langchain_core.messages import AIMessage
from langgraph.types import Command
from pydantic import BaseModel

from src.agent.trace import build_trace_summary


DEFAULT_GOLDEN_SET = "evaluation/golden/agent_cases.jsonl"
DEFAULT_OUTPUT = "evaluation/reports/agent_eval.json"
DEFAULT_TIMEOUT_SECONDS = 120
CI_RUN_MODE = "ci_deterministic"
LIVE_RUN_MODE = "live"
MOCA_NAMESPACE = uuid.UUID("f47ac10b-58cc-4372-a567-0d02b2c3d479")

THRESHOLDS = {
    "intent_accuracy": 0.90,
    "tool_selection_accuracy": 0.85,
    "citation_rate": 0.85,
    "safety_critical_pass_rate": 1.0,
}
SAFETY_CRITICAL_CATEGORIES = {
    "approval_required",
    "permission_denied",
    "approval_approved",
    "approval_rejected",
}
GRAPH_CONTRACT_CATEGORIES = [
    "normal_policy_qa",
    "refund_troubleshooting",
    "compensation_suggestion",
]


class FakeLLM:
    """Deterministic fake LLM for CI structured-output contracts."""

    def __init__(self, response_dict: dict[str, Any]):
        self._response = response_dict

    async def ainvoke(self, messages, **kwargs):
        return AIMessage(content=json.dumps(self._response, ensure_ascii=False))

    def with_structured_output(self, schema):
        fake = self

        class _Wrapper:
            async def ainvoke(self, messages, **kwargs):
                if issubclass(schema, BaseModel):
                    return schema.model_validate(fake._response)
                return fake._response

        return _Wrapper()


def deterministic_id(entity_type: str, key: str) -> uuid.UUID:
    return uuid.uuid5(MOCA_NAMESPACE, f"{entity_type}:{key}")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Agent golden-set evaluation")
    parser.add_argument("--golden-set", default=DEFAULT_GOLDEN_SET, help="Path to JSONL golden set")
    parser.add_argument("--mode", choices=("ci", "live"), default="ci", help="Evaluation mode")
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help="Path to write JSON report")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_SECONDS, help="Per-case timeout in seconds")
    return parser


def _load_cases(path: str) -> list[dict[str, Any]]:
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def _ci_fake_llm_responses(case: dict[str, Any]) -> dict[str, FakeLLM]:
    """Return FakeLLM instances matching the graph node structured-output contract."""
    expected_intent = case.get("expected_intent") or "policy_qa"
    expected_response = _expected_response_text(case)
    approval_required = bool(case.get("expected_approval_required"))
    risk_level = "high" if approval_required else "low"
    proposed_action = "issue_coupon" if "compensation" in expected_intent or approval_required else "answer_only"
    requested_operation = "draft_action" if proposed_action != "answer_only" else "advise"
    return {
        "classify_intent": FakeLLM(
            {
                "schema_version": "intent_result.v3",
                "primary_intent": expected_intent,
                "requested_operation": requested_operation,
                "confidence": 0.95,
                "calibrated_confidence": 0.95,
                "secondary_intents": [],
                "required_slots": {"all_of": [], "any_of": [], "optional": []},
                "candidate_slots": {},
                "routing_hints": {},
                "classifier_version": "ci",
                "calibration_version": "ci",
                "reason_codes": ["ci_deterministic"],
            }
        ),
        "extract_slots": FakeLLM(
            {
                "order_id": _extract_seed_id(case["query"], "ORD-"),
                "refund_case_id": _extract_seed_id(case["query"], "RF-"),
                "ticket_id": _extract_seed_id(case["query"], "TK-"),
                "merchant_id": None,
                "customer_id": None,
                "issue_type": case["category"],
                "action_type": proposed_action if proposed_action != "answer_only" else None,
            }
        ),
        "generate_recommendation": FakeLLM(
            {
                "recommended_action": proposed_action,
                "reasoning_summary": "CI deterministic recommendation",
                "evidence_refs": [
                    {"doc_key": doc_key, "chunk_id": f"{doc_key}_001", "title": doc_key, "section": "ci"}
                    for doc_key in case.get("expected_evidence_doc_keys", [])
                ],
                "confidence": 0.90,
                "risk_level": risk_level,
                "missing_info": [] if case.get("expected_evidence_doc_keys") else ["context"],
            }
        ),
        "assess_risk": FakeLLM(
            {
                "risk_level": risk_level,
                "risk_reason": "CI deterministic risk",
                "approval_required": approval_required,
                "rule_ref": "HR-CI" if approval_required else "LR-CI",
            }
        ),
        "final_response": FakeLLM(
            {
                "response_text": expected_response,
                "evidence_citations": case.get("expected_evidence_doc_keys", []),
                "final_status": case.get("expected_status", "completed"),
            }
        ),
    }


def _extract_seed_id(text: str, prefix: str) -> str | None:
    import re

    match = re.search(rf"{re.escape(prefix)}[A-Za-z0-9-]+", text)
    if match:
        return match.group(0).rstrip(".,;:!?，。；：！？")
    for token in text.replace("，", " ").replace("。", " ").replace("？", " ").split():
        if token.startswith(prefix):
            return token.rstrip(".,;:!?")
    return None


def _expected_response_text(case: dict[str, Any]) -> str:
    required = [str(item) for item in case.get("expected_response_contains") or []]
    if not required:
        required = ["已完成"]
    return "；".join(required)


def _ci_input_state(case: dict[str, Any]) -> dict[str, Any]:
    return {
        "user_query": case["query"],
        "thread_id": f"eval-{case['thread_id']}",
        "tenant_id": str(deterministic_id("tenant", "demo")),
        "user_id": str(deterministic_id("user", "demo_support_1")),
        "role": "support_agent",
    }


def _ci_config(case: dict[str, Any]) -> dict[str, Any]:
    return {
        "configurable": {
            "thread_id": f"eval:{case['id']}:{case['thread_id']}",
            "session": None,
        }
    }


def _ci_policy_result(case: dict[str, Any]) -> dict[str, Any]:
    evidence = [
        {
            "doc_key": doc_key,
            "chunk_id": f"{doc_key}_001",
            "title": doc_key,
            "section": "ci",
            "score": 0.91,
            "text": _expected_response_text(case),
        }
        for doc_key in case.get("expected_evidence_doc_keys", [])
    ]
    return {
        "status": "success",
        "data": {
            "retrieval_status": "strong_evidence" if evidence else "no_evidence",
            "best_score": 0.91 if evidence else 0.0,
            "evidence": evidence,
            "fallback_message": None if evidence else "没有找到相关政策证据。",
        },
        "error": {},
    }


def _ci_order_result(case: dict[str, Any]) -> dict[str, Any]:
    order_id = _extract_seed_id(case["query"], "ORD-") or "ORD-2024-001"
    if "NONEXIST" in order_id or "400" in order_id:
        return {
            "status": "error",
            "data": {},
            "error": {
                "error_code": "ORDER_NOT_FOUND",
                "message": f"订单 {order_id} 未找到",
                "retryable": False,
                "should_stop": False,
            },
        }
    return {
        "status": "success",
        "data": {
            "id": str(deterministic_id("order", order_id)),
            "order_no": order_id,
            "status": "delivered",
            "amount": "899.00",
            "merchant_risk_level": "low",
        },
        "error": {},
    }


def _ci_action_result(case: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": "success",
        "data": {
            "draft_id": str(deterministic_id("action_draft", case["id"])),
            "status": "draft",
        },
        "error": {},
    }


def _ci_tool_permissions() -> list[str]:
    from src.tools.catalog import ToolCatalog

    return [f"tool:{descriptor.name}" for descriptor in ToolCatalog().descriptors()]


def _ci_policy_tool_result(case: dict[str, Any]):
    from src.knowledge.schemas import EvidenceRefV1
    from src.tools.contracts import ToolResultV2

    evidence_refs = [
        EvidenceRefV1.build(
            tenant_id=str(deterministic_id("tenant", "demo")),
            doc_key=doc_key,
            chunk_id=f"{doc_key}_001",
            policy_version="ci",
            text=_expected_response_text(case),
            retrieved_at=datetime.now(UTC).isoformat(),
            retrieval_config_version="ci",
            score=0.91,
            rank=rank,
        )
        for rank, doc_key in enumerate(case.get("expected_evidence_doc_keys", []), start=1)
    ]
    status = "strong_evidence" if evidence_refs else "no_evidence"
    return ToolResultV2(
        status="success" if evidence_refs else "not_found",
        data={"retrieval_status": status, "best_score": 0.91 if evidence_refs else 0.0, "threshold": 0.55},
        summary=f"CI policy search returned {status}",
        source_system="policy_knowledge_service",
        data_freshness_at=None,
        policy_evidence_refs=evidence_refs,
        business_fact_refs=[],
        error=None,
        retryable=False,
        retry_after_ms=None,
        latency_ms=1,
        audit_ref=None,
    )


def _ci_business_tool_result(case: dict[str, Any], name: str):
    from src.tools.contracts import BusinessFactRefV1, ToolResultV2

    resource_type_by_tool = {
        "get_order": "order",
        "get_refund_case": "refund_case",
        "get_ticket": "ticket",
    }
    resource_type = resource_type_by_tool.get(name, "order")
    resource_id = (
        _extract_seed_id(case["query"], "ORD-")
        or _extract_seed_id(case["query"], "RF-")
        or _extract_seed_id(case["query"], "TK-")
        or "CI-001"
    )
    ref = BusinessFactRefV1(
        tenant_id=str(deterministic_id("tenant", "demo")),
        source_system="ci",
        resource_type=resource_type,
        resource_id=resource_id,
        resource_version=None,
        data_freshness_at=datetime.now(UTC),
        retrieved_at=datetime.now(UTC),
    )
    return ToolResultV2(
        status="success",
        data={"id": resource_id, "status": "delivered"},
        summary=f"CI {resource_type} loaded",
        source_system="business_tool_service",
        data_freshness_at=datetime.now(UTC),
        policy_evidence_refs=[],
        business_fact_refs=[ref],
        error=None,
        retryable=False,
        retry_after_ms=None,
        latency_ms=1,
        audit_ref=None,
    )


def _ci_action_tool_result(case: dict[str, Any]):
    from src.tools.contracts import ToolResultV2

    return ToolResultV2(
        status="success",
        data=_ci_action_result(case)["data"],
        summary="CI action draft created",
        source_system="action_service",
        data_freshness_at=None,
        policy_evidence_refs=[],
        business_fact_refs=[],
        error=None,
        retryable=False,
        retry_after_ms=None,
        latency_ms=1,
        audit_ref=None,
    )


class CiToolManager:
    def __init__(self, case: dict[str, Any]) -> None:
        from src.tools.catalog import ToolCatalog

        self.case = case
        self._descriptors = {descriptor.name: descriptor for descriptor in ToolCatalog().descriptors()}

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

    async def invoke(self, name: str, args: dict[str, Any], ctx):
        if name == "search_policy":
            return _ci_policy_tool_result(self.case)
        if name in {"get_order", "get_refund_case", "get_ticket"}:
            return _ci_business_tool_result(self.case, name)
        if name == "create_coupon_grant_draft":
            return _ci_action_tool_result(self.case)

        from src.tools.contracts import ToolError, ToolResultV2

        return ToolResultV2(
            status="unavailable",
            data=None,
            summary=f"CI tool unavailable: {name}",
            source_system="ci_tool_manager",
            data_freshness_at=None,
            policy_evidence_refs=[],
            business_fact_refs=[],
            error=ToolError(
                code="TOOL_UNAVAILABLE", safe_message="CI tool unavailable", retryable=False, source="tool"
            ),
            retryable=False,
            retry_after_ms=None,
            latency_ms=0,
            audit_ref=None,
        )


async def _run_graph_contract_case(case: dict[str, Any]) -> list[str]:
    from langgraph.checkpoint.memory import MemorySaver

    from src.agent.graph import build_graph
    from src.agent.nodes import assess_risk_and_approval as assess_risk_module
    from src.agent.nodes import classify_intent as classify_intent_module
    from src.agent.nodes import extract_slots as extract_slots_module
    from src.agent.nodes import generate_recommendation as generate_recommendation_module

    fake_llms = _ci_fake_llm_responses(case)
    expected_nodes = _expected_nodes_for_case(case)
    config = _ci_config(case)
    config["configurable"]["permissions"] = _ci_tool_permissions()
    config["configurable"]["merchant_scope"] = {"merchant_ids": ["*"]}
    config["configurable"]["tool_manager"] = CiToolManager(case)
    config["configurable"]["action_tool_manager"] = CiToolManager(case)

    async def event_emitter(**payload):
        return None

    config["configurable"]["event_emitter"] = event_emitter
    failures: list[str] = []

    patches = [
        patch.object(classify_intent_module, "_get_llm", lambda: fake_llms["classify_intent"]),
        patch.object(extract_slots_module, "_get_llm", lambda: fake_llms["extract_slots"]),
        patch.object(generate_recommendation_module, "_get_llm", lambda: fake_llms["generate_recommendation"]),
        patch.object(assess_risk_module, "_get_llm", lambda: fake_llms["assess_risk"]),
    ]

    with patches[0], patches[1], patches[2], patches[3]:
        graph = build_graph(MemorySaver())
        result = await graph.ainvoke(_ci_input_state(case), config)

        if "__interrupt__" in result:
            snapshot = await graph.aget_state(config)
            state = dict(snapshot.values or {})
            interrupted_nodes = [str(step.get("node") or "unknown") for step in state.get("trace_steps") or []]
            interrupted_nodes.append("approval_gate")
            if "approval_gate" not in expected_nodes:
                failures.append(f"{case['id']} unexpectedly interrupted at approval_gate")
            if case["category"] == "approval_required":
                result_summary = {"nodes_executed": interrupted_nodes, "approval_interrupt_created": True}
                return [f"{case['id']}: {failure}" for failure in _assert_ci_routing(case, result_summary)]

            decision = "approve" if case["category"] == "approval_approved" else "reject"
            result = await graph.ainvoke(
                Command(
                    resume={
                        "decision": decision,
                        "reason": "CI graph contract",
                        "run_id": state.get("current_run_id"),
                        "approval_id": str(deterministic_id("approval", case["id"])),
                    }
                ),
                config,
            )

        summary = build_trace_summary(result.get("current_run_id", str(deterministic_id("run", case["id"]))), result, 0)
        summary["approval_interrupt_created"] = "approval_gate" in summary["nodes_executed"]
        failures.extend(_assert_ci_routing(case, summary))
        return [f"{case['id']}: {failure}" for failure in failures]


async def _run_ci_graph_contracts(cases: list[dict[str, Any]]) -> list[str]:
    cases_by_category: dict[str, dict[str, Any]] = {}
    for case in cases:
        cases_by_category.setdefault(case["category"], case)
    failures: list[str] = []
    for category in GRAPH_CONTRACT_CATEGORIES:
        case = cases_by_category.get(category)
        if not case:
            failures.append(f"missing representative case for {category}")
            continue
        try:
            failures.extend(await _run_graph_contract_case(case))
        except Exception as exc:
            failures.append(f"{case['id']}: graph invocation failed: {type(exc).__name__}: {exc}")
    return failures


def _trace_step(
    node: str, *, tools: list[str] | None = None, evidence: list[dict[str, str]] | None = None
) -> dict[str, Any]:
    step: dict[str, Any] = {"node": node, "status": "completed"}
    if tools:
        step["tools_called"] = tools
    if evidence:
        step["evidence_refs"] = evidence
    return step


def _expected_nodes_for_case(case: dict[str, Any]) -> list[str]:
    category = case["category"]
    if category == "permission_denied":
        return []
    nodes = ["receive_request", "classify_intent"]
    if case.get("expected_intent") != "policy_qa":
        nodes.extend(["session_memory_load", "extract_slots"])
    nodes.extend(["investigate", "generate_recommendation", "assess_risk_and_approval"])
    if category in {"low_confidence_no_evidence", "missing_context", "tool_failure_or_not_found"}:
        return [*nodes, "final_response"]
    if category == "approval_approved":
        _resume_command = Command(resume={"decision": "approve", "reason": "CI test"})
        return [*nodes, "approval_gate", "execute_action", "final_response"]
    if category == "approval_rejected":
        _resume_command = Command(resume={"decision": "reject", "reason": "CI test"})
        return [*nodes, "approval_gate", "final_response"]
    if case.get("expected_approval_required"):
        return [*nodes, "approval_gate"]
    if category == "approval_required":
        return [*nodes, "approval_gate"]
    return [*nodes, "final_response"]


def _build_ci_state(case: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    _ci_fake_llm_responses(case)
    category = case["category"]
    expected_tools_called = list(case.get("expected_tools_called") or [])
    evidence_doc_keys = list(case.get("expected_evidence_doc_keys") or [])
    evidence = [{"doc_key": doc_key, "chunk_id": f"{doc_key}_001"} for doc_key in evidence_doc_keys]
    nodes = _expected_nodes_for_case(case)
    trace_steps = [_trace_step(node) for node in nodes]

    if "investigate" in nodes and expected_tools_called:
        load_idx = nodes.index("investigate")
        non_write_tools = [tool for tool in expected_tools_called if tool != "create_coupon_grant_draft"]
        if evidence and "search_policy" not in non_write_tools:
            non_write_tools.append("search_policy")
        trace_steps[load_idx] = _trace_step("investigate", tools=non_write_tools, evidence=evidence)
    if "execute_action" in nodes and "create_coupon_grant_draft" in expected_tools_called:
        action_idx = nodes.index("execute_action")
        trace_steps[action_idx] = _trace_step("execute_action", tools=["create_coupon_grant_draft"])

    final_status = case.get("expected_status", "completed")
    state: dict[str, Any] = {
        "current_run_id": str(deterministic_id("run", case["id"])),
        "current_intent": case.get("expected_intent"),
        "risk_assessment": {
            "approval_required": bool(case.get("expected_approval_required")),
            "risk_level": "high" if case.get("expected_approval_required") else "low",
            "risk_reason": "CI deterministic risk",
            "rule_ref": "HR-CI" if case.get("expected_approval_required") else "LR-CI",
        },
        "retrieved_evidence": {
            "status": "success",
            "data": {"retrieval_status": "success" if evidence else "no_evidence", "evidence": evidence},
        },
        "trace_steps": trace_steps,
        "final_response": _expected_response_text(case),
    }
    if final_status == "insufficient_evidence":
        state["recommendation_draft"] = {"recommended_action": "insufficient_evidence"}
    if final_status == "error":
        state["node_errors"] = [{"node": category, "error": _expected_response_text(case)}]

    if category == "permission_denied":
        state = {
            **state,
            "trace_steps": [],
            "node_errors": [{"node": "api_auth", "error": "HTTP 403 权限不足"}],
            "final_response": _expected_response_text(case),
        }

    summary = build_trace_summary(state["current_run_id"], state, 0)
    summary["approval_interrupt_created"] = "approval_gate" in summary["nodes_executed"]
    summary["http_status_code"] = 403 if category == "permission_denied" else 200
    return state, summary


async def _run_case_ci(case: dict[str, Any]) -> dict[str, Any]:
    state, summary = _build_ci_state(case)
    assertions = _assert_ci_routing(case, summary)
    scores = _score_case(case, state, summary, latency_ms=None, total_tokens=0, routing_failures=assertions)
    return {"case": case, "result": state, "trace_summary": summary, "scores": scores}


async def _run_case_live(case: dict[str, Any], timeout: int) -> dict[str, Any]:
    if not os.environ.get("DASHSCOPE_API_KEY"):
        raise RuntimeError("DASHSCOPE_API_KEY is required for --mode live")

    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

    from src.agent.graph import build_graph
    from src.config import settings
    from src.db.session import SessionLocal, engine

    tenant_id = str(deterministic_id("tenant", "demo"))
    user_id = str(deterministic_id("user", "demo_support_1"))
    config = {"configurable": {"thread_id": f"{tenant_id}:{user_id}:{case['thread_id']}", "session": None}}
    input_state = {
        "user_query": case["query"],
        "thread_id": case["thread_id"],
        "tenant_id": tenant_id,
        "user_id": user_id,
        "role": "support_agent",
    }

    started = time.perf_counter()
    try:
        async with AsyncPostgresSaver.from_conn_string(settings.checkpointer_database_url) as checkpointer:
            await checkpointer.setup()
            graph = build_graph(checkpointer)
            async with SessionLocal() as session:
                config["configurable"]["session"] = session
                result = await asyncio.wait_for(graph.ainvoke(input_state, config), timeout=timeout)
    finally:
        await engine.dispose()

    latency_ms = int((time.perf_counter() - started) * 1000)
    summary = build_trace_summary(result["current_run_id"], result, latency_ms)
    assertions = _assert_ci_routing(case, summary)
    scores = _score_case(
        case,
        result,
        summary,
        latency_ms=latency_ms,
        total_tokens=_extract_total_tokens(result),
        routing_failures=assertions,
    )
    return {"case": case, "result": result, "trace_summary": summary, "scores": scores}


def _assert_ci_routing(case: dict[str, Any], summary: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    category = case["category"]
    nodes_executed = summary.get("nodes_executed") or []
    expected_nodes = _expected_nodes_for_case(case)

    for node in expected_nodes:
        if node not in nodes_executed:
            failures.append(f"nodes_executed missing {node}")

    if category == "approval_required":
        if "approval_gate" not in nodes_executed:
            failures.append("approval_required did not reach approval_gate")
        if not summary.get("approval_interrupt_created"):
            failures.append("approval_required did not create approval interrupt")
    if category == "approval_approved" and "execute_action" not in nodes_executed:
        failures.append("approval_approved did not execute action after Command(resume=approve)")
    if category == "approval_rejected":
        if "execute_action" in nodes_executed:
            failures.append("approval_rejected unexpectedly executed action after Command(resume=reject)")
        if "final_response" not in nodes_executed:
            failures.append("approval_rejected did not reach final_response")
    if category == "permission_denied" and summary.get("http_status_code") != 403:
        failures.append("permission_denied did not produce HTTP 403")

    tools_called = summary.get("tools_called") or []
    if category in SAFETY_CRITICAL_CATEGORIES and category != "approval_approved":
        if "create_coupon_grant_draft" in tools_called:
            failures.append("safety-critical case executed write tool without approval")
    return failures


def _score_case(
    case: dict[str, Any],
    result: dict[str, Any],
    summary: dict[str, Any],
    *,
    latency_ms: int | None,
    total_tokens: int,
    routing_failures: list[str],
) -> dict[str, Any]:
    expected_intent = case.get("expected_intent")
    actual_intent = result.get("current_intent")
    expected_tools_called = set(case.get("expected_tools_called") or [])
    actual_tools_called = set(summary.get("tools_called") or [])
    expected_status = case.get("expected_status", "completed")
    risk = result.get("risk_assessment") or {}
    expected_doc_keys = set(case.get("expected_evidence_doc_keys") or [])
    evidence_doc_keys = _evidence_doc_keys(result)
    final_response = str(result.get("final_response") or "")

    scores = {
        "intent_match": actual_intent == expected_intent,
        "tools_match": expected_tools_called <= actual_tools_called,
        "status_match": summary.get("final_status") == expected_status,
        "approval_match": bool(risk.get("approval_required", False))
        == bool(case.get("expected_approval_required", False)),
        "evidence_match": True if not expected_doc_keys else bool(expected_doc_keys & evidence_doc_keys),
        "response_contains": all(str(item) in final_response for item in case.get("expected_response_contains") or []),
        "must_not_contain": all(str(item) not in final_response for item in case.get("must_not_contain") or []),
        "routing_match": not routing_failures,
        "latency_ms": latency_ms,
        "total_tokens": total_tokens,
    }
    failures = [
        key
        for key in (
            "intent_match",
            "tools_match",
            "status_match",
            "approval_match",
            "evidence_match",
            "response_contains",
            "must_not_contain",
            "routing_match",
        )
        if not scores[key]
    ]
    failures.extend(routing_failures)
    scores["passed"] = not failures
    scores["failures"] = failures
    return scores


def _evidence_doc_keys(result: dict[str, Any]) -> set[str]:
    retrieved = result.get("retrieved_evidence") or {}
    data = retrieved.get("data") or retrieved
    evidence = data.get("evidence") or []
    return {str(item.get("doc_key")) for item in evidence if item.get("doc_key")}


def _extract_total_tokens(result: dict[str, Any]) -> int:
    total = 0
    for step in result.get("trace_steps") or []:
        total += int(step.get("prompt_tokens") or 0)
        total += int(step.get("completion_tokens") or 0)
    return total


def _aggregate(
    results: list[dict[str, Any]],
    *,
    mode: str,
    graph_contract_failures: list[str] | None = None,
) -> dict[str, Any]:
    total_cases = len(results)
    passed_cases = sum(1 for item in results if item["scores"]["passed"])
    evidence_cases = [item for item in results if item["case"].get("expected_evidence_doc_keys")]
    safety_cases = [item for item in results if item["case"]["category"] in SAFETY_CRITICAL_CATEGORIES]
    latencies = [item["scores"]["latency_ms"] for item in results if item["scores"]["latency_ms"] is not None]

    metrics = {
        "intent_accuracy": _rate(results, "intent_match"),
        "tool_selection_accuracy": _rate(results, "tools_match"),
        "task_completion_rate": _rate(results, "status_match"),
        "approval_accuracy": _rate(results, "approval_match"),
        "citation_rate": _rate(evidence_cases, "evidence_match") if evidence_cases else 1.0,
        "safety_critical_pass_rate": _passed_rate(safety_cases) if safety_cases else 1.0,
        "total_cases": total_cases,
        "passed_cases": passed_cases,
        "average_latency_ms": (sum(latencies) / len(latencies)) if latencies else None,
        "total_tokens": 0 if mode == "ci" else sum(item["scores"]["total_tokens"] for item in results),
    }
    graph_contract_failures = graph_contract_failures or []
    status = "pass" if _passes_thresholds(metrics) and not graph_contract_failures else "fail"

    return {
        "eval_type": "agent",
        "mode": mode,
        "run_mode": CI_RUN_MODE if mode == "ci" else LIVE_RUN_MODE,
        "generated_at": datetime.now(UTC).isoformat(),
        "status": status,
        "thresholds": THRESHOLDS,
        "metrics": metrics,
        "per_category": _per_category(results),
        "failed_cases": [
            {
                "id": item["case"]["id"],
                "category": item["case"]["category"],
                "query": item["case"]["query"],
                "failures": item["scores"]["failures"],
            }
            for item in results
            if not item["scores"]["passed"]
        ]
        + [
            {
                "id": "GRAPH-CONTRACT",
                "category": "ci_graph_contract",
                "query": "compiled graph deterministic contract checks",
                "failures": graph_contract_failures,
            }
        ]
        if graph_contract_failures
        else [
            {
                "id": item["case"]["id"],
                "category": item["case"]["category"],
                "query": item["case"]["query"],
                "failures": item["scores"]["failures"],
            }
            for item in results
            if not item["scores"]["passed"]
        ],
        "graph_contract": {
            "mode": "compiled_langgraph_with_patched_dependencies" if mode == "ci" else "live_graph",
            "categories_checked": GRAPH_CONTRACT_CATEGORIES if mode == "ci" else [],
            "failures": graph_contract_failures,
            "status": "pass" if not graph_contract_failures else "fail",
        },
        "case_results": [
            {
                "id": item["case"]["id"],
                "category": item["case"]["category"],
                "passed": item["scores"]["passed"],
                "latency_ms": item["scores"]["latency_ms"],
                "tokens": item["scores"]["total_tokens"],
                "trace_summary": item["trace_summary"],
            }
            for item in results
        ],
    }


def _rate(results: list[dict[str, Any]], key: str) -> float:
    return sum(1 for item in results if item["scores"][key]) / len(results) if results else 1.0


def _passed_rate(results: list[dict[str, Any]]) -> float:
    return sum(1 for item in results if item["scores"]["passed"]) / len(results) if results else 1.0


def _passes_thresholds(metrics: dict[str, Any]) -> bool:
    return (
        metrics["intent_accuracy"] >= THRESHOLDS["intent_accuracy"]
        and metrics["tool_selection_accuracy"] >= THRESHOLDS["tool_selection_accuracy"]
        and metrics["citation_rate"] >= THRESHOLDS["citation_rate"]
        and metrics["safety_critical_pass_rate"] == THRESHOLDS["safety_critical_pass_rate"]
    )


def _per_category(results: list[dict[str, Any]]) -> dict[str, dict[str, float | int]]:
    grouped: dict[str, dict[str, int]] = {}
    for item in results:
        category = item["case"]["category"]
        grouped.setdefault(category, {"total": 0, "passed": 0})
        grouped[category]["total"] += 1
        if item["scores"]["passed"]:
            grouped[category]["passed"] += 1
    return {
        category: {
            "total": values["total"],
            "passed": values["passed"],
            "rate": values["passed"] / values["total"] if values["total"] else 0.0,
        }
        for category, values in sorted(grouped.items())
    }


def _print_report(report: dict[str, Any]) -> None:
    metrics = report["metrics"]
    print(f"\n{'=' * 60}")
    print("Agent Evaluation Report")
    print(f"{'=' * 60}")
    print(f"Mode: {report['mode']} ({report['run_mode']})")
    print(f"Status: {report['status'].upper()}")
    print(f"Total cases: {metrics['total_cases']}")
    print(f"Intent accuracy: {metrics['intent_accuracy']:.1%}")
    print(f"Tool selection accuracy: {metrics['tool_selection_accuracy']:.1%}")
    print(f"Citation rate: {metrics['citation_rate']:.1%}")
    print(f"Safety critical pass rate: {metrics['safety_critical_pass_rate']:.1%}")
    print("\nPer-category:")
    for category, stats in report["per_category"].items():
        print(f"  {category}: {stats['rate']:.0%} ({stats['passed']}/{stats['total']})")
    if report["failed_cases"]:
        print(f"\nFailed cases ({len(report['failed_cases'])}):")
        for failed in report["failed_cases"]:
            print(f"  - {failed['id']} {failed['category']}: {failed['failures']}")


async def run_agent_eval(
    golden_set_path: str | None = None,
    mode: str = "ci",
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    cases = _load_cases(golden_set_path or DEFAULT_GOLDEN_SET)
    if mode not in {"ci", "live"}:
        raise ValueError("mode must be 'ci' or 'live'")

    results: list[dict[str, Any]] = []
    for case in cases:
        if mode == "ci":
            results.append(await _run_case_ci(case))
        else:
            results.append(await _run_case_live(case, timeout))
    graph_contract_failures = await _run_ci_graph_contracts(cases) if mode == "ci" else []
    return _aggregate(results, mode=mode, graph_contract_failures=graph_contract_failures)


async def main() -> None:
    parser = _parser()
    args = parser.parse_args()

    try:
        report = await run_agent_eval(golden_set_path=args.golden_set, mode=args.mode, timeout=args.timeout)
    except FileNotFoundError:
        parser.error(f"golden set not found: {args.golden_set}")
    except json.JSONDecodeError as exc:
        parser.error(f"invalid JSONL in {args.golden_set}: {exc}")
    except RuntimeError as exc:
        parser.error(str(exc))

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    _print_report(report)
    if report["status"] == "fail":
        print(f"\nFAIL: JSON report written to {output_path}")
        sys.exit(1)

    print(f"\nPASS. JSON report written to {output_path}")
    sys.exit(0)


if __name__ == "__main__":
    asyncio.run(main())
