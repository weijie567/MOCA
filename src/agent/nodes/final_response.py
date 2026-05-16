from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from src.agent.prompts import INSUFFICIENT_EVIDENCE_RESPONSE
from src.agent.state import AgentState


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _trace_step(status: str, started_at: str) -> dict[str, Any]:
    return {
        "node": "final_response",
        "status": status,
        "started_at": started_at,
        "completed_at": _now_iso(),
        "model_name": "deterministic-template",
        "prompt_tokens": None,
        "completion_tokens": None,
        "provider_latency_ms": None,
        "retry_count": 0,
        "metrics_json": None,
    }


def _insufficient_response(draft: dict[str, Any]) -> str:
    missing_info = draft.get("missing_info") or []
    if not missing_info:
        return INSUFFICIENT_EVIDENCE_RESPONSE
    return f"{INSUFFICIENT_EVIDENCE_RESPONSE}\n缺少信息：{'、'.join(str(item) for item in missing_info)}"


def _retrieval_error_response(draft: dict[str, Any]) -> str:
    missing_info = draft.get("missing_info") or []
    suffix = f"原因：{'、'.join(str(item) for item in missing_info)}" if missing_info else ""
    return f"系统暂时无法检索政策依据，请稍后重试或联系人工客服。{suffix}"


def _citation_summary(evidence_refs: list[dict[str, Any]]) -> str:
    if not evidence_refs:
        return ""
    citations = []
    for ref in evidence_refs[:3]:
        doc_key = ref.get("doc_key") or "unknown_doc"
        chunk_id = ref.get("chunk_id") or "unknown_chunk"
        title = ref.get("title") or "政策依据"
        section = ref.get("section") or "相关章节"
        citations.append(f"根据 {doc_key} / {chunk_id}，{title} - {section}")
    return "；".join(citations)


def _completed_response(draft: dict[str, Any], risk_assessment: dict[str, Any]) -> str:
    action = draft.get("recommended_action") or "建议按已检索到的政策依据处理。"
    reasoning = draft.get("reasoning_summary") or "已根据当前知识库证据生成建议。"
    citations = _citation_summary(draft.get("evidence_refs") or [])
    parts = [f"建议：{action}", f"理由：{reasoning}"]
    if citations:
        parts.append(f"依据：{citations}。")
    if risk_assessment.get("approval_required"):
        risk_reason = risk_assessment.get("risk_reason") or "命中风险规则"
        parts.append(f"风险提示：{risk_reason}，需要人工审批后执行。")
    return "\n".join(parts)


async def final_response(state: AgentState) -> dict:
    started_at = _now_iso()
    draft = state.get("recommendation_draft") or {}
    if draft.get("recommended_action") == "retrieval_error":
        return {
            "final_response": _retrieval_error_response(draft),
            "trace_steps": (state.get("trace_steps") or []) + [_trace_step("error", started_at)],
        }
    if draft.get("recommended_action") in {"insufficient_evidence", "citation_invalid"}:
        return {
            "final_response": _insufficient_response(draft),
            "trace_steps": (state.get("trace_steps") or []) + [_trace_step("completed", started_at)],
        }
    response_text = _completed_response(draft, state.get("risk_assessment") or {})
    return {
        "final_response": response_text,
        "llm_outputs": {
            **(state.get("llm_outputs") or {}),
            "final_response": {
                "response_text": response_text,
                "evidence_citations": [
                    f"{ref.get('doc_key')} / {ref.get('chunk_id')}" for ref in draft.get("evidence_refs") or []
                ],
                "final_status": "completed",
                "mode": "deterministic-template",
            },
        },
        "trace_steps": (state.get("trace_steps") or []) + [_trace_step("completed", started_at)],
    }
