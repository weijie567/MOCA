from __future__ import annotations

import re
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import yaml
from langchain_openai import ChatOpenAI
from pydantic import ValidationError

from src.agent.prompts import ASSESS_RISK_SYSTEM
from src.agent.schemas import RiskAssessment
from src.agent.state import AgentState
from src.config import settings

RISK_RULES_PATH = Path("rules/risk_rules.yaml")


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _get_llm() -> ChatOpenAI:
    return ChatOpenAI(
        model=settings.llm_model,
        openai_api_key=settings.dashscope_api_key,
        openai_api_base=settings.embedding_base_url,
        temperature=settings.llm_temperature,
        max_tokens=settings.llm_max_tokens,
        timeout=settings.llm_timeout_seconds,
    )


def _trace_step(status: str, started_at: str) -> dict[str, Any]:
    return {
        "node": "assess_risk_and_approval",
        "status": status,
        "started_at": started_at,
        "completed_at": _now_iso(),
        "model_name": settings.llm_model,
        "prompt_tokens": None,
        "completion_tokens": None,
    }


def _load_risk_rules() -> dict[str, Any]:
    with RISK_RULES_PATH.open("r", encoding="utf-8") as file:
        return yaml.safe_load(file) or {}


def _money_value(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _extract_compensation_amount(draft: dict[str, Any], context: dict[str, Any]) -> Decimal | None:
    for key in ("compensation_amount", "amount", "approved_amount", "requested_amount"):
        amount = _money_value(draft.get(key))
        if amount is not None:
            return amount

    text = " ".join(str(draft.get(key) or "") for key in ("recommended_action", "reasoning_summary"))
    match = re.search(r"(\d+(?:\.\d+)?)\s*(?:CNY|元|人民币)", text, flags=re.IGNORECASE)
    if match:
        return _money_value(match.group(1))

    refund_case = context.get("refund_case") or {}
    return _money_value(refund_case.get("approved_amount") or refund_case.get("requested_amount"))


def _rule_threshold(rule: dict[str, Any], operator: str) -> Decimal | None:
    pattern = rf"compensation_amount\s*{re.escape(operator)}\s*(\d+(?:\.\d+)?)"
    match = re.search(pattern, rule.get("condition", ""))
    return _money_value(match.group(1)) if match else None


def _deterministic_rule_match(draft: dict[str, Any], context: dict[str, Any], rules: dict[str, Any]) -> dict[str, Any] | None:
    action = str(draft.get("recommended_action") or "")
    amount = _extract_compensation_amount(draft, context)
    order = context.get("order") or {}
    merchant_risk_level = context.get("merchant_risk_level") or order.get("merchant_risk_level")

    for rule in rules.get("high_risk") or []:
        condition = rule.get("condition", "")
        threshold = _rule_threshold(rule, ">")
        if threshold is not None and amount is not None and amount > threshold:
            return rule
        if "full_refund" in condition and "full_refund" in action and order.get("status") == "delivered":
            return rule
        if "merchant_risk_level" in condition and merchant_risk_level == "high":
            return rule
    return None


def _fallback_risk(draft: dict[str, Any], context: dict[str, Any], rules: dict[str, Any]) -> dict[str, Any]:
    if draft.get("recommended_action") == "insufficient_evidence":
        return {
            "risk_level": "low",
            "risk_reason": "No action is recommended because evidence is insufficient.",
            "approval_required": False,
            "rule_ref": "LR-01",
        }

    high_rule = _deterministic_rule_match(draft, context, rules)
    if high_rule:
        return {
            "risk_level": "high",
            "risk_reason": high_rule.get("description") or "High risk rule matched.",
            "approval_required": True,
            "rule_ref": high_rule.get("id"),
        }

    low_rule = (rules.get("low_risk") or [{}])[0]
    return {
        "risk_level": "low",
        "risk_reason": low_rule.get("description") or "No high risk rule matched.",
        "approval_required": False,
        "rule_ref": low_rule.get("id"),
    }


async def assess_risk_and_approval(state: AgentState) -> dict:
    started_at = _now_iso()
    rules = _load_risk_rules()
    draft = state.get("recommendation_draft") or {}
    context = state.get("business_context") or {}

    if draft.get("recommended_action") == "insufficient_evidence":
        assessment = _fallback_risk(draft, context, rules)
        return {
            "risk_assessment": assessment,
            "trace_steps": (state.get("trace_steps") or []) + [_trace_step("completed", started_at)],
        }

    messages: list[dict[str, str]] = [
        {"role": "system", "content": ASSESS_RISK_SYSTEM},
        {"role": "user", "content": f"Risk rules: {rules}\nRecommendation: {draft}\nBusiness context: {context}"},
    ]
    structured_llm = _get_llm().with_structured_output(RiskAssessment)
    last_error: str | None = None

    for attempt in range(2):
        try:
            result = await structured_llm.ainvoke(messages)
            assessment = result.model_dump()
            high_rule = _deterministic_rule_match(draft, context, rules)
            if high_rule:
                assessment.update(
                    {
                        "risk_level": "high",
                        "risk_reason": high_rule.get("description") or assessment["risk_reason"],
                        "approval_required": True,
                        "rule_ref": high_rule.get("id"),
                    }
                )
            outputs = {**(state.get("llm_outputs") or {}), "assess_risk_and_approval": assessment}
            return {
                "risk_assessment": assessment,
                "llm_outputs": outputs,
                "trace_steps": (state.get("trace_steps") or []) + [_trace_step("completed", started_at)],
            }
        except (ValidationError, ValueError) as exc:
            last_error = str(exc)
            if attempt == 0:
                messages.append(
                    {
                        "role": "user",
                        "content": f"Validation failed: {last_error}. Respond with valid JSON.",
                    }
                )

    return {
        "risk_assessment": _fallback_risk(draft, context, rules),
        "node_errors": (state.get("node_errors") or [])
        + [{"node": "assess_risk_and_approval", "error": last_error, "retry_count": 2}],
        "trace_steps": (state.get("trace_steps") or []) + [_trace_step("error", started_at)],
    }
