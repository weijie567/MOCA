from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from langchain_core.runnables import RunnableConfig

from src.agent.state import AgentState
from src.knowledge.retrieval import PolicyRetrievalEngine
from src.knowledge.schemas import ClaimVerificationBundleV1
from src.knowledge.service import PolicyKnowledgeService


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


async def claim_verify(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    started_at = _now_iso()
    service = _policy_knowledge_service(config)
    try:
        raw_bundle = await service.verify_claims(
            material_claims=list(state.get("material_claims") or []),
            verified_evidence_package=state.get("verified_evidence_package"),
            business_context=_mapping_or_empty(state.get("business_context")),
            proposed_action=_mapping_or_none(state.get("proposed_action")),
        )
        bundle = (
            raw_bundle
            if isinstance(raw_bundle, ClaimVerificationBundleV1)
            else ClaimVerificationBundleV1.model_validate(raw_bundle)
        )
    except Exception:
        bundle = _claim_verify_error_bundle()

    return _node_result(state, bundle, started_at)


def _policy_knowledge_service(config: RunnableConfig | None) -> Any:
    configurable = _configurable(config)
    service = configurable.get("policy_knowledge_service") or configurable.get("knowledge_service")
    if service is not None and hasattr(service, "verify_claims"):
        return service
    session = configurable.get("session")
    if session is not None:
        return PolicyKnowledgeService(PolicyRetrievalEngine(session))
    return _MissingPolicyKnowledgeService()


class _MissingPolicyKnowledgeService:
    async def verify_claims(self, **_: Any) -> ClaimVerificationBundleV1:
        raise RuntimeError("policy knowledge service unavailable")


def _node_result(
    state: AgentState,
    bundle: ClaimVerificationBundleV1,
    started_at: str,
) -> dict[str, Any]:
    bundle_data = bundle.model_dump(mode="json")
    safe_support_refs = [ref.model_dump(mode="json") for ref in bundle.safe_support_refs]
    safe_ref_ids = [ref["evidence_id"] for ref in safe_support_refs if isinstance(ref, dict) and ref.get("evidence_id")]
    return {
        "claim_verification_bundle": bundle_data,
        "blocked_claims": list(bundle.blocked_claims),
        "safe_support_refs": safe_support_refs,
        "verifier_status": bundle.overall_status,
        "verification_route": _legacy_verification_route(bundle),
        "verifier_reason_codes": list(bundle.reason_codes),
        "verifier_safe_citation_refs": safe_ref_ids,
        "trace_steps": (state.get("trace_steps") or []) + [_trace_step(bundle, started_at)],
    }


def _trace_step(bundle: ClaimVerificationBundleV1, started_at: str) -> dict[str, Any]:
    return {
        "node": "claim_verify",
        "status": "error" if bundle.overall_status == "error" else "completed",
        "started_at": started_at,
        "completed_at": _now_iso(),
        "provider_latency_ms": None,
        "retry_count": 0,
        "metrics_json": {
            "claim_verification_status": bundle.overall_status,
            "claim_verification_route": bundle.route,
            "claim_result_count": len(bundle.claim_results),
            "blocked_claim_count": len(bundle.blocked_claims),
            "safe_support_ref_count": len(bundle.safe_support_refs),
            "reason_code_count": len(bundle.reason_codes),
        },
    }


def _legacy_verification_route(bundle: ClaimVerificationBundleV1) -> str:
    if bundle.route == "continue" and bundle.overall_status in {"verified", "not_required"}:
        return "allow"
    if bundle.route == "manual_review" or bundle.overall_status == "manual_review":
        return "manual_review"
    return "refuse"


def _claim_verify_error_bundle() -> ClaimVerificationBundleV1:
    return ClaimVerificationBundleV1(
        overall_status="error",
        route="final_response",
        claim_results=[],
        blocked_claims=[],
        safe_support_refs=[],
        reason_codes=["claim_verify_error"],
        verifier_policy_version="material_claim_verifier.v1",
    )


def _mapping_or_empty(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _mapping_or_none(value: Any) -> Mapping[str, Any] | None:
    return value if isinstance(value, Mapping) else None


def _configurable(config: RunnableConfig | None) -> dict[str, Any]:
    if not isinstance(config, Mapping):
        return {}
    value = config.get("configurable") or {}
    return dict(value) if isinstance(value, Mapping) else {}
