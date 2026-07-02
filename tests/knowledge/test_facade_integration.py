from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from src.agent.nodes.claim_verify import claim_verify
from src.agent.nodes import generate_recommendation as recommendation_module
from src.agent.nodes.investigate import investigate
from src.agent.nodes.final_response import final_response
from src.agent.nodes.rag_context_build import rag_context_build
from src.knowledge.config import RERANK_CONFIG_VERSION, RETRIEVAL_CONFIG_VERSION
from src.knowledge.schemas import (
    ClaimVerificationBundleV1,
    ClaimVerificationResultV1,
    EvidenceRefV1,
    KnowledgeSearchResult,
    VerifiedEvidencePackageV1,
)
from src.platform.trusted_context import MerchantScopeV1, TrustedContext
from src.tools.catalog import ToolCatalog
from src.tools.contracts import ToolCallContext, ToolInvocationOutcome, ToolPolicyDecision, ToolResultV2, ToolViewV1
from src.tools.projection import ToolResultProjector
from tests.agent.conftest import FakeLLM


TENANT_ID = "11111111-1111-1111-1111-111111111111"


def _base_state() -> dict:
    return {
        "thread_id": "facade-integration-thread",
        "tenant_id": TENANT_ID,
        "user_id": "user-001",
        "role": "support_agent",
        "user_query": "退款超时规则是什么？",
        "current_intent": "policy_qa",
        "current_run_id": "run-001",
        "run_started_at": "2026-06-07T00:00:00+00:00",
        "business_context": {},
        "evidence_refs": [],
        "trace_steps": [],
        "proposed_action": None,
    }


def _evidence(*, text: str = "退款超时时，应核实支付通道和退款状态。") -> EvidenceRefV1:
    return EvidenceRefV1.build(
        tenant_id=TENANT_ID,
        doc_key="policy_refund_timeout",
        chunk_id="chunk_001",
        policy_version="v3",
        text=text,
        retrieved_at="2026-06-07T00:00:00+00:00",
        retrieval_config_version=RETRIEVAL_CONFIG_VERSION,
        score=0.82,
        rank=1,
    )


def _search_result(
    *,
    status: str,
    best_score: float,
    evidence_refs: list[EvidenceRefV1],
) -> KnowledgeSearchResult:
    return KnowledgeSearchResult(
        status=status,
        retrieval_config_version=RETRIEVAL_CONFIG_VERSION,
        rerank_config_version=RERANK_CONFIG_VERSION,
        best_score=best_score,
        threshold=0.55,
        evidence_refs=evidence_refs,
    )


class FakePolicyPlatform:
    def __init__(self, search_result: KnowledgeSearchResult) -> None:
        self._descriptors = {descriptor.name: descriptor for descriptor in ToolCatalog().descriptors()}
        self.search_result = search_result
        self.calls: list[tuple[str, dict, ToolCallContext]] = []
        self._projector = ToolResultProjector()
        self.last_visibility_decisions = None

    def descriptor(self, name: str):
        return self._descriptors.get(name)

    def event_family(self, name: str) -> str | None:
        descriptor = self._descriptors.get(name)
        if descriptor is None:
            return None
        if descriptor.event_family == "rag_retrieval_*":
            return "rag_retrieval"
        if descriptor.event_family == "tool_call_*":
            return "tool_call"
        return None

    async def visible_tools(
        self,
        *,
        caller: str,
        ctx: ToolCallContext,
        session=None,
    ) -> list[ToolViewV1]:
        from src.tools.policy import ToolPolicyEngine, project_prompt_safe_input_schema

        engine = ToolPolicyEngine()
        decisions = engine.visibility_decisions(caller=caller, ctx=ctx)
        self.last_visibility_decisions = decisions
        views = []
        for decision in decisions:
            if decision.decision != "visible":
                continue
            descriptor = self._descriptors.get(decision.tool_name)
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
        args: dict,
        ctx: ToolCallContext,
        *,
        session=None,
    ) -> ToolInvocationOutcome:
        self.calls.append((tool_name, args, ctx))
        result = ToolResultV2(
            status="not_found" if self.search_result.status == "no_evidence" else "success",
            data={
                "retrieval_status": self.search_result.status,
                "best_score": self.search_result.best_score,
                "threshold": self.search_result.threshold,
                "summary": self.search_result.summary,
            },
            summary=self.search_result.summary or f"Policy search returned {self.search_result.status}",
            source_system="policy_knowledge_service",
            data_freshness_at=None,
            policy_evidence_refs=self.search_result.evidence_refs,
            business_fact_refs=[],
            error=None,
            retryable=False,
            retry_after_ms=None,
            latency_ms=1,
            audit_ref=None,
        )
        projection = self._projector.project(
            tool_name=tool_name,
            result=result,
            tool_call_id=ctx.tool_call_id,
        )
        decision = ToolPolicyDecision(
            tool_name=tool_name,
            caller=ctx.caller_node,
            decision_stage="runtime_auth",
            decision="allowed",
            reason_codes=["visible"],
            required_scopes=[],
            matched_scope=None,
            policy_version="tool_policy.v1",
            data_classification="internal",
            runtime_available=True,
        )
        return ToolInvocationOutcome(
            tool_result=result,
            projection=projection,
            policy_decision=decision,
            policy_event_id=None,
        )


def _recommendation(*, chunk_id: str = "chunk_001", reasoning: str = "根据规则应处理退款。") -> dict:
    return {
        "recommended_action": "建议退款",
        "reasoning_summary": reasoning,
        "evidence_refs": [
            {
                "doc_key": "policy_refund_timeout",
                "chunk_id": chunk_id,
                "title": "退款超时规则",
                "section": "第一条",
            }
        ],
        "confidence": 0.85,
        "risk_level": "low",
        "missing_info": [],
    }


async def _run_path(
    monkeypatch: pytest.MonkeyPatch,
    *,
    search_result: KnowledgeSearchResult,
    recommendation: dict | None,
) -> dict:
    if recommendation is None:
        monkeypatch.setattr(
            recommendation_module,
            "_get_llm",
            lambda: pytest.fail("LLM must not run for a retrieval safety draft"),
        )
    else:
        monkeypatch.setattr(recommendation_module, "_get_llm", lambda: FakeLLM(recommendation))

    class FakePolicyKnowledgeService:
        async def build_verified_context(self, *, candidate_evidence_refs, knowledge_context, **_kwargs):
            evidence_map = {ref.evidence_id: ref for ref in candidate_evidence_refs}
            citations = [
                {
                    "citation_id": f"citation-{index}",
                    "display_label": f"{ref.doc_key} / {ref.chunk_id}",
                    "snippet": "退款超时时，应核实支付通道和退款状态。",
                    "metadata": {
                        "doc_key": ref.doc_key,
                        "chunk_id": ref.chunk_id,
                        "policy_version": ref.policy_version,
                    },
                }
                for index, ref in enumerate(candidate_evidence_refs, start=1)
            ]
            citation_map = {
                citation["citation_id"]: [ref.evidence_id]
                for citation, ref in zip(citations, candidate_evidence_refs, strict=True)
            }
            return VerifiedEvidencePackageV1(
                package_id=f"verified-evidence:{knowledge_context.run_id}:facade",
                status="verified" if candidate_evidence_refs else "no_evidence",
                evidence_items=[],
                citation_map=citation_map,
                evidence_map=evidence_map,
                prompt_projection={"citations": citations},
                verifier_projection={"safe_refs": list(evidence_map), "evidence_snippets": []},
                replay_snapshot_refs=[],
                debug_projection={},
                stale_refs=[],
                conflict_refs=[],
                rejected_candidate_refs=[],
                reason_codes=[],
                policy_version=candidate_evidence_refs[0].policy_version if candidate_evidence_refs else "v3",
                retrieval_config_version=RETRIEVAL_CONFIG_VERSION,
            )

        async def verify_claims(self, *, material_claims, verified_evidence_package, **_kwargs):
            claims = list(material_claims or [])
            if not claims:
                return ClaimVerificationBundleV1(
                    overall_status="not_required",
                    route="continue",
                    claim_results=[],
                    blocked_claims=[],
                    safe_support_refs=[],
                    reason_codes=["no_material_claims"],
                    verifier_policy_version="material_claim_verifier.v1",
                )
            package = VerifiedEvidencePackageV1.model_validate(verified_evidence_package)
            unsupported = any("free vacation" in str(_claim_value(claim, "claim_text")) for claim in claims)
            safe_refs = list(package.evidence_map.values()) if not unsupported else []
            return ClaimVerificationBundleV1(
                overall_status="manual_review" if unsupported else "verified",
                route="manual_review" if unsupported else "continue",
                claim_results=[
                    ClaimVerificationResultV1(
                        claim_id=str(_claim_value(claim, "claim_id")),
                        claim_type=_claim_value(claim, "claim_type"),
                        support_status="unsupported" if unsupported else "supported",
                        supporting_evidence_refs=safe_refs,
                        business_fact_refs=_claim_value(claim, "business_fact_refs") or [],
                        rule_checks=[],
                        semantic_review_status="failed" if unsupported else "not_needed",
                        allows_user_visible_claim=not unsupported,
                        allows_action_recommendation=not unsupported,
                    )
                    for claim in claims
                ],
                blocked_claims=[str(_claim_value(claim, "claim_id")) for claim in claims] if unsupported else [],
                safe_support_refs=safe_refs,
                reason_codes=["semantic_support_failed"] if unsupported else [],
                verifier_policy_version="material_claim_verifier.v1",
            )

    state = _base_state()
    state["_investigate_plan"] = [
        {"next_tool": "search_policy", "args": {"query": state["user_query"]}, "reason": "policy"}
    ]
    events: list[dict] = []
    platform = FakePolicyPlatform(search_result)
    trusted_context = TrustedContext(
        tenant_id=TENANT_ID,
        user_id=state["user_id"],
        role="support",
        permissions=["tool:search_policy"],
        merchant_scope=MerchantScopeV1(merchant_ids=[]),
        session_id=None,
        thread_id=state["thread_id"],
        run_id=state["current_run_id"],
        trace_id="facade-trace",
        locale=None,
    )

    async def event_emitter(**payload):
        events.append(payload)

    service = FakePolicyKnowledgeService()
    configurable = {
        "session": AsyncMock(),
        "permissions": ["tool:search_policy"],
        "merchant_scope": {"merchant_ids": []},
        "tool_platform": platform,
        "trusted_context": trusted_context.model_dump(mode="json"),
        "event_emitter": event_emitter,
        "policy_knowledge_service": service,
    }
    investigate_output = await investigate(
        state,
        {"configurable": configurable},
    )
    state.update(investigate_output)
    rag_context_output = await rag_context_build(state, {"configurable": configurable})
    state.update(rag_context_output)
    recommendation_output = await recommendation_module.generate_recommendation(
        state,
        {"configurable": configurable},
    )
    state.update(recommendation_output)
    claim_output = await claim_verify(state, {"configurable": configurable})
    state.update(claim_output)
    response_output = await final_response(state)
    state.update(response_output)
    return state


def _claim_value(claim, key: str):
    if isinstance(claim, dict):
        return claim.get(key)
    return getattr(claim, key)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status", "best_score"),
    [("strong_evidence", 0.82), ("partial_evidence", 0.62)],
)
async def test_facade_path_preserves_actionable_status_and_canonical_evidence(
    monkeypatch,
    status,
    best_score,
):
    evidence = _evidence()

    state = await _run_path(
        monkeypatch,
        search_result=_search_result(status=status, best_score=best_score, evidence_refs=[evidence]),
        recommendation=_recommendation(reasoning="退款超时时，应核实支付通道和退款状态。"),
    )

    assert state["retrieved_evidence"]["status"] == status
    assert state["retrieved_evidence"]["evidence_refs"][0]["schema_version"] == "evidence_ref.v1"
    assert state["evidence_refs"][0]["evidence_id"] == evidence.evidence_id
    assert state["evidence_refs"][0]["text_hash"] == evidence.text_hash
    assert state["recommendation_draft"]["citation_validation"]["is_valid"] is True
    assert "policy_refund_timeout / chunk_001" in state["final_response"]


@pytest.mark.asyncio
async def test_no_evidence_produces_insufficient_draft_without_action(monkeypatch):
    state = await _run_path(
        monkeypatch,
        search_result=_search_result(status="no_evidence", best_score=0.0, evidence_refs=[]),
        recommendation=None,
    )

    assert state["retrieved_evidence"]["status"] == "no_evidence"
    assert state["recommendation_draft"]["recommended_action"] == "insufficient_evidence"
    assert state["proposed_action"] is None
    assert state["evidence_refs"] == []


@pytest.mark.asyncio
async def test_all_invalid_membership_produces_citation_invalid_without_action(monkeypatch):
    state = await _run_path(
        monkeypatch,
        search_result=_search_result(status="strong_evidence", best_score=0.82, evidence_refs=[_evidence()]),
        recommendation=_recommendation(chunk_id="missing"),
    )

    assert state["recommendation_draft"]["recommended_action"] == "citation_invalid"
    assert state["recommendation_draft"]["confidence"] == 0.0
    assert state["recommendation_draft"]["evidence_refs"] == []
    assert state["proposed_action"] is None
    assert state["llm_outputs"]["final_response"]["final_status"] == "insufficient_evidence"


@pytest.mark.asyncio
async def test_present_evidence_id_passes_membership_without_semantic_support(monkeypatch):
    evidence = _evidence(text="This evidence discusses refund timing only.")

    state = await _run_path(
        monkeypatch,
        search_result=_search_result(status="partial_evidence", best_score=0.62, evidence_refs=[evidence]),
        recommendation=_recommendation(reasoning="The merchant receives a free vacation."),
    )

    assert state["recommendation_draft"]["citation_validation"]["is_valid"] is True
    assert state["verification_route"] != "allow"
    assert state["blocked_claims"]
