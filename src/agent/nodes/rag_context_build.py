from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from typing import Any

from langchain_core.runnables import RunnableConfig
from pydantic import ValidationError

from src.agent.state import AgentState
from src.knowledge.config import RETRIEVAL_CONFIG_VERSION
from src.knowledge.retrieval import PolicyRetrievalEngine
from src.knowledge.schemas import EvidenceRefV1, KnowledgeContext, VerifiedEvidencePackageV1
from src.knowledge.service import PolicyKnowledgeService
from src.platform.context_projections import project_to_knowledge_context
from src.platform.trusted_context import TrustedContext
from src.tools.contracts import BusinessFactRefV1


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


async def rag_context_build(state: AgentState, config: RunnableConfig) -> dict:
    started_at = _now_iso()
    candidates, invalid_candidate_count = _candidate_evidence_refs(state)
    knowledge_context = _knowledge_context_from_config(config)
    if knowledge_context is None:
        package = _build_error_package(
            candidates=candidates,
            knowledge_context=_fallback_knowledge_context(),
            retrieval_config_version=_retrieval_config_version(candidates),
            reason_code="missing_trusted_context",
        )
        return _node_result(state, package, started_at)

    service = _policy_knowledge_service(config)
    try:
        package = await service.build_verified_context(
            candidate_evidence_refs=candidates,
            business_fact_refs=_business_fact_refs_from_state(state),
            knowledge_context=knowledge_context,
            evidence_policy=_evidence_policy_from_state(state, candidates),
        )
    except Exception:
        package = _build_error_package(
            candidates=candidates,
            knowledge_context=knowledge_context,
            retrieval_config_version=_retrieval_config_version(candidates),
            reason_code="rag_context_build_error",
        )

    if invalid_candidate_count:
        package = _annotate_invalid_candidates(package, invalid_candidate_count)
    return _node_result(state, package, started_at)


def _candidate_evidence_refs(state: AgentState) -> tuple[list[EvidenceRefV1], int]:
    valid_refs: list[EvidenceRefV1] = []
    invalid_count = 0
    seen: set[str] = set()

    for raw in _candidate_values(state):
        try:
            ref = raw if isinstance(raw, EvidenceRefV1) else EvidenceRefV1.model_validate(raw)
        except Exception:
            invalid_count += 1
            continue
        key = ref.evidence_id
        if key in seen:
            continue
        seen.add(key)
        valid_refs.append(ref)
    return valid_refs, invalid_count


def _candidate_values(state: AgentState) -> Iterable[Any]:
    yield from _iter_direct_candidate_value(state.get("retrieved_evidence"))
    yield from _iter_candidate_sequence(state.get("policy_evidence"))
    retrieved = state.get("retrieved_evidence")
    if isinstance(retrieved, Mapping):
        yield from _iter_candidate_sequence(retrieved.get("evidence_refs"))


def _iter_candidate_sequence(value: Any) -> Iterable[Any]:
    if value is None:
        return
    if isinstance(value, EvidenceRefV1):
        yield value
        return
    if isinstance(value, list | tuple):
        for item in value:
            yield item
        return
    if isinstance(value, Mapping):
        if value.get("evidence_id") is not None:
            yield value
        return


def _iter_direct_candidate_value(value: Any) -> Iterable[Any]:
    if value is None:
        return
    if isinstance(value, EvidenceRefV1):
        yield value
        return
    if isinstance(value, list | tuple):
        for item in value:
            yield item
        return
    if isinstance(value, Mapping) and value.get("evidence_id") is not None:
        yield value


def _knowledge_context_from_config(config: RunnableConfig | None) -> KnowledgeContext | None:
    configurable = _configurable(config)
    raw_context = configurable.get("trusted_context")
    if raw_context is None:
        return None
    try:
        trusted = raw_context if isinstance(raw_context, TrustedContext) else TrustedContext.model_validate(raw_context)
    except ValidationError:
        return None
    effective_at = str(
        configurable.get("effective_at")
        or configurable.get("run_started_at")
        or configurable.get("request_started_at")
        or _now_iso()
    )
    return project_to_knowledge_context(trusted, effective_at=effective_at)


def _fallback_knowledge_context() -> KnowledgeContext:
    return KnowledgeContext(
        tenant_id="00000000-0000-0000-0000-000000000000",
        user_id="unknown",
        role="support",
        merchant_scope=[],
        run_id="unknown-run",
        trace_id="unknown-trace",
        locale=None,
        effective_at=_now_iso(),
    )


def _policy_knowledge_service(config: RunnableConfig | None) -> Any:
    configurable = _configurable(config)
    service = configurable.get("policy_knowledge_service") or configurable.get("knowledge_service")
    if service is not None and hasattr(service, "build_verified_context"):
        return service
    session = configurable.get("session")
    if session is not None:
        return PolicyKnowledgeService(PolicyRetrievalEngine(session))
    return _MissingPolicyKnowledgeService()


class _MissingPolicyKnowledgeService:
    async def build_verified_context(self, **_: Any) -> VerifiedEvidencePackageV1:
        raise RuntimeError("policy knowledge service unavailable")


def _business_fact_refs_from_state(state: AgentState) -> list[BusinessFactRefV1]:
    raw_refs: list[Any] = []
    business_context = state.get("business_context")
    if isinstance(business_context, Mapping):
        raw_refs.extend(business_context.get("business_fact_refs") or [])
    for tool_result in state.get("tool_results") or []:
        if isinstance(tool_result, Mapping):
            raw_refs.extend(tool_result.get("business_fact_refs") or [])

    refs: list[BusinessFactRefV1] = []
    for raw in raw_refs:
        try:
            refs.append(raw if isinstance(raw, BusinessFactRefV1) else BusinessFactRefV1.model_validate(raw))
        except Exception:
            continue
    return refs


def _evidence_policy_from_state(
    state: AgentState,
    candidates: list[EvidenceRefV1],
) -> dict[str, Any]:
    retrieved = state.get("retrieved_evidence") if isinstance(state.get("retrieved_evidence"), Mapping) else {}
    policy: dict[str, Any] = {
        "evidence_required": True,
        "retrieval_config_version": _retrieval_config_version(candidates),
    }
    for key in ("doc_type", "risk_level", "policy_version"):
        value = state.get(key) or retrieved.get(key)
        if value is not None:
            policy[key] = str(value)
    risk_hints = state.get("risk_hints")
    if isinstance(risk_hints, list):
        policy["risk_hints"] = [dict(item) for item in risk_hints if isinstance(item, Mapping)]
    return policy


def _retrieval_config_version(candidates: list[EvidenceRefV1]) -> str:
    if candidates:
        return candidates[0].retrieval_config_version
    return RETRIEVAL_CONFIG_VERSION


def _build_error_package(
    *,
    candidates: list[EvidenceRefV1],
    knowledge_context: KnowledgeContext,
    retrieval_config_version: str,
    reason_code: str,
) -> VerifiedEvidencePackageV1:
    return VerifiedEvidencePackageV1(
        package_id=f"verified-evidence:{knowledge_context.run_id}:build-error",
        status="build_error",
        evidence_items=[],
        citation_map={},
        evidence_map={},
        prompt_projection={},
        verifier_projection={"safe_refs": [], "evidence_snippets": [], "business_fact_refs": []},
        replay_snapshot_refs=[],
        debug_projection={"reason_codes": [reason_code]},
        stale_refs=[],
        conflict_refs=[],
        rejected_candidate_refs=list(candidates),
        reason_codes=[reason_code],
        policy_version=candidates[0].policy_version if candidates else "unknown",
        retrieval_config_version=retrieval_config_version,
    )


def _annotate_invalid_candidates(
    package: VerifiedEvidencePackageV1,
    invalid_candidate_count: int,
) -> VerifiedEvidencePackageV1:
    reason_codes = [*package.reason_codes]
    if "candidate_ref_invalid" not in reason_codes:
        reason_codes.append("candidate_ref_invalid")
    debug_projection = dict(package.debug_projection)
    debug_projection["invalid_candidate_count"] = invalid_candidate_count
    return package.model_copy(
        update={
            "reason_codes": reason_codes,
            "debug_projection": debug_projection,
        }
    )


def _node_result(
    state: AgentState,
    package: VerifiedEvidencePackageV1,
    started_at: str,
) -> dict[str, Any]:
    package_data = package.model_dump(mode="json")
    return {
        "rag_context_status": package.status,
        "verified_evidence_package": package_data,
        "citation_map": package_data["citation_map"],
        "evidence_map": package_data["evidence_map"],
        "trace_steps": (state.get("trace_steps") or []) + [_trace_step(package, started_at)],
    }


def _trace_step(package: VerifiedEvidencePackageV1, started_at: str) -> dict[str, Any]:
    return {
        "node": "rag_context_build",
        "status": "completed" if package.status != "build_error" else "error",
        "started_at": started_at,
        "completed_at": _now_iso(),
        "provider_latency_ms": None,
        "retry_count": 0,
        "metrics_json": {
            "rag_context_status": package.status,
            "reason_code_count": len(package.reason_codes),
            "verified_evidence_count": len(package.evidence_map),
            "rejected_candidate_count": len(package.rejected_candidate_refs),
            "stale_ref_count": len(package.stale_refs),
            "conflict_ref_count": len(package.conflict_refs),
        },
    }


def _configurable(config: RunnableConfig | None) -> dict[str, Any]:
    if not isinstance(config, Mapping):
        return {}
    value = config.get("configurable") or {}
    return dict(value) if isinstance(value, Mapping) else {}
