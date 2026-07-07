from __future__ import annotations

from typing import Any

import pytest

from src.agent.nodes.final_response import final_response
from src.knowledge.config import RETRIEVAL_CONFIG_VERSION
from src.knowledge.schemas import EvidenceRefV1


VERIFIER_TRACE = "SHOULD_NOT_LEAK_VERIFIER_TRACE"
RAW_PROVENANCE = "SHOULD_NOT_LEAK_RAW_PROVENANCE"
SOURCE_BLOCK_ID = "refund-policy:policy_pdf:text:source-block-private"
PRIVATE_REASONING = "SHOULD_NOT_LEAK_PRIVATE_REASONING"
DEBUG_PROJECTION = "SHOULD_NOT_LEAK_DEBUG_PROJECTION"
RAW_REASON_PAYLOAD = "SHOULD_NOT_LEAK_RAW_REASON_PAYLOAD"
INTERNAL_REASON_CODES = {
    "unsupported",
    "missing_citation",
    "conflicting_evidence",
    "stale_evidence",
    "unauthorized_evidence",
    "text_hash_mismatch",
    "latest_version_invalid",
    "ocr_low_confidence",
    "business_fact_missing",
    "semantic_ambiguous",
    "regenerate_route",
}


def _evidence_ref(tenant_id: str = "11111111-1111-1111-1111-111111111111") -> dict[str, Any]:
    return EvidenceRefV1.build(
        tenant_id=tenant_id,
        doc_key="policy_refund_timeout",
        chunk_id="chunk_001",
        policy_version="v3",
        text="Refund timeout compensation requires verified policy evidence.",
        retrieved_at="2026-06-19T00:00:00.000Z",
        retrieval_config_version=RETRIEVAL_CONFIG_VERSION,
        score=0.91,
        rank=1,
    ).model_dump(mode="json")


def _verified_package(
    *,
    status: str,
    ref: dict[str, Any] | None = None,
    reason_codes: list[str] | None = None,
) -> dict[str, Any]:
    evidence_ref = ref or _evidence_ref()
    return {
        "schema_version": "verified_evidence_package.v1",
        "package_id": "pkg-final-response",
        "status": status,
        "evidence_items": [],
        "citation_map": {"C1": [evidence_ref["evidence_id"]]},
        "evidence_map": {evidence_ref["evidence_id"]: evidence_ref},
        "prompt_projection": {"citations": [{"citation_id": "C1", "evidence_id": evidence_ref["evidence_id"]}]},
        "verifier_projection": {"safe_refs": [evidence_ref["evidence_id"]]},
        "replay_snapshot_refs": [evidence_ref["evidence_id"]],
        "debug_projection": {
            "debug_projection": DEBUG_PROJECTION,
            "verifier_prompt": VERIFIER_TRACE,
            "source_block_id": SOURCE_BLOCK_ID,
            "private_reasoning": PRIVATE_REASONING,
        },
        "stale_refs": [],
        "conflict_refs": [],
        "rejected_candidate_refs": [evidence_ref],
        "reason_codes": reason_codes or [status],
        "policy_version": "v3",
        "retrieval_config_version": RETRIEVAL_CONFIG_VERSION,
    }


def _claim_bundle(
    *,
    route: str,
    overall_status: str,
    ref: dict[str, Any] | None = None,
    blocked_claims: list[str] | None = None,
    reason_codes: list[str] | None = None,
) -> dict[str, Any]:
    evidence_ref = ref or _evidence_ref()
    return {
        "schema_version": "claim_verification_bundle.v1",
        "overall_status": overall_status,
        "route": route,
        "claim_results": [
            {
                "schema_version": "claim_verification_result.v1",
                "claim_id": "claim-action-1",
                "claim_type": "action_recommendation",
                "support_status": "unsupported",
                "supporting_evidence_refs": [],
                "business_fact_refs": [],
                "rule_checks": [{"rule": "policy_support_required", "passed": False}],
                "semantic_review_status": "not_needed",
                "allows_user_visible_claim": False,
                "allows_action_recommendation": False,
            }
        ],
        "blocked_claims": blocked_claims or ["claim-action-1"],
        "safe_support_refs": [evidence_ref],
        "reason_codes": reason_codes or ["unsupported"],
        "verifier_policy_version": "claim-verifier.v1",
        "raw_reason_payload": RAW_REASON_PAYLOAD,
        "verifier_prompt": VERIFIER_TRACE,
        "private_reasoning": PRIVATE_REASONING,
    }


def _verification_state(
    *,
    outcome: str,
    route: str,
    reason_codes: list[str],
) -> dict[str, Any]:
    return {
        "overall_outcome": outcome,
        "allows_recommendation": False,
        "route": {
            "route": route,
            "selected_by": "backend",
            "model_selected": False,
            "decision_source": "phase22_verifier",
        },
        "reason_codes": reason_codes,
        "debug_trace": {
            "verifier_prompt": VERIFIER_TRACE,
            "raw_provenance": RAW_PROVENANCE,
            "source_block_id": SOURCE_BLOCK_ID,
            "private_reasoning": PRIVATE_REASONING,
        },
    }


def _state(base_state: dict[str, Any], *, outcome: str, route: str, reason_codes: list[str]) -> dict[str, Any]:
    return {
        **base_state,
        "rag_verification": _verification_state(outcome=outcome, route=route, reason_codes=reason_codes),
        "trace_steps": [{"node": "generate_recommendation", "status": "completed"}],
        "recommendation_draft": {
            "recommended_action": "issue_coupon",
            "reasoning_summary": "Model proposed compensation, but verifier did not allow it.",
            "evidence_refs": [
                {
                    "doc_key": "policy_refund_timeout",
                    "chunk_id": "chunk_001",
                    "title": "Refund policy",
                    "section": "Compensation",
                }
            ],
            "confidence": 0.91,
            "risk_level": "high",
            "missing_info": [],
        },
        "business_context": {
            "order": {"order_no": "ORD-1001", "status": "delivered", "item_name": "测试商品"},
        },
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("outcome", "route", "reason_codes", "expected_status", "expected_phrase"),
    [
        ("unsupported", "regenerate_route", ["unsupported", "missing_citation"], "insufficient_evidence", "重新生成"),
        ("insufficient", "insufficient_evidence", ["missing_citation"], "insufficient_evidence", "没有找到足够证据"),
        ("conflicting", "manual_review", ["conflicting_evidence"], "manual_review", "人工复核"),
        ("stale", "manual_review", ["stale_evidence"], "manual_review", "人工复核"),
        ("unauthorized", "refuse", ["unauthorized_evidence"], "refused", "无法基于当前政策证据"),
        ("hash_mismatch", "refuse", ["text_hash_mismatch"], "refused", "无法基于当前政策证据"),
        ("latest_version_invalid", "refuse", ["latest_version_invalid"], "refused", "无法基于当前政策证据"),
        ("ocr_low_confidence", "manual_review", ["ocr_low_confidence"], "manual_review", "人工复核"),
        (
            "business_fact_missing",
            "insufficient_evidence",
            ["business_fact_missing"],
            "insufficient_evidence",
            "业务事实不足",
        ),
        ("semantic_ambiguous", "manual_review", ["semantic_ambiguous"], "manual_review", "人工复核"),
    ],
)
async def test_final_response_renders_safe_non_allow_verifier_outcomes_without_internal_codes(
    base_state: dict[str, Any],
    outcome: str,
    route: str,
    reason_codes: list[str],
    expected_status: str,
    expected_phrase: str,
) -> None:
    """RTE-05: non-allow verifier routes get safe user wording and no debug leakage."""
    result = await final_response(_state(base_state, outcome=outcome, route=route, reason_codes=reason_codes))

    response_text = result["final_response"]

    assert expected_phrase in response_text
    assert result["llm_outputs"]["final_response"]["final_status"] == expected_status
    assert result["llm_outputs"]["final_response"]["verification_route"] == route
    assert result["llm_outputs"]["final_response"]["route_selected_by"] == "backend"
    assert result["llm_outputs"]["final_response"]["model_selected_route"] is False
    assert result["llm_outputs"]["final_response"]["safe_projection_source"] == "historical_compatibility_projection"
    assert result["llm_outputs"]["final_response"]["verification_authoritative"] is False
    for internal_code in INTERNAL_REASON_CODES:
        assert internal_code not in response_text
    for unsafe in (VERIFIER_TRACE, RAW_PROVENANCE, SOURCE_BLOCK_ID, PRIVATE_REASONING):
        assert unsafe not in response_text


@pytest.mark.asyncio
async def test_final_response_does_not_turn_manual_review_verification_into_action_success(
    base_state: dict[str, Any],
) -> None:
    """RTE-05: manual-review verifier state cannot be worded as approval, draft, or action success."""
    state = _state(
        base_state,
        outcome="conflicting",
        route="manual_review",
        reason_codes=["conflicting_evidence", "semantic_ambiguous"],
    )
    state.update(
        {
            "risk_assessment": {"approval_required": True, "risk_reason": "high risk"},
            "approval_result": {"decision": "approve"},
            "action_draft": {"draft_id": "draft-should-not-appear", "status": "draft_created"},
            "draft_outcome": {"status": "not_executed_demo", "draft_id": "draft-should-not-appear"},
        }
    )

    result = await final_response(state)

    assert "人工复核" in result["final_response"]
    assert "draft-should-not-appear" not in result["final_response"]
    assert "审批结果" not in result["final_response"]
    assert "草稿已创建" not in result["final_response"]


@pytest.mark.asyncio
async def test_final_response_renders_safe_rag_context_block_without_package_debug_leakage(
    base_state: dict[str, Any],
) -> None:
    """APF-13: blocked package states produce safe final text, never debug_projection internals."""
    state = {
        **base_state,
        "rag_context_status": "invalid_hash",
        "verified_evidence_package": _verified_package(
            status="invalid_hash",
            reason_codes=["text_hash_mismatch", "source_block_internal"],
        ),
        "recommendation_draft": {
            "recommended_action": "issue_coupon",
            "reasoning_summary": f"Unsafe raw policy reasoning {PRIVATE_REASONING}",
            "evidence_refs": [_evidence_ref()],
            "missing_info": [DEBUG_PROJECTION, "text_hash_mismatch"],
        },
        "business_context": {
            "order": {"order_no": "ORD-1001", "status": "delivered", "item_name": "测试商品"},
        },
        "proposed_action": {"action_type": "coupon_grant"},
        "approval_result": {"decision": "approve"},
        "action_draft": {"draft_id": "draft-should-not-appear", "status": "draft_created"},
        "draft_outcome": {"status": "not_executed_demo", "draft_id": "draft-should-not-appear"},
    }

    result = await final_response(state)
    response_text = result["final_response"]

    assert "证据" in response_text
    assert "草稿已创建" not in response_text
    assert "draft-should-not-appear" not in response_text
    assert "issue_coupon" not in response_text
    assert result["llm_outputs"]["final_response"]["final_status"] in {"insufficient_evidence", "manual_review"}
    for unsafe in (DEBUG_PROJECTION, VERIFIER_TRACE, SOURCE_BLOCK_ID, PRIVATE_REASONING, "debug_projection"):
        assert unsafe not in response_text


@pytest.mark.asyncio
async def test_final_response_renders_safe_claim_bundle_block_without_raw_reason_payload(
    base_state: dict[str, Any],
) -> None:
    """APF-14: blocked claim bundles produce safe final text without verifier_prompt/private_reasoning."""
    ref = _evidence_ref()
    state = {
        **base_state,
        "rag_context_status": "verified",
        "verified_evidence_package": _verified_package(status="verified", ref=ref),
        "claim_verification_bundle": _claim_bundle(route="manual_review", overall_status="blocked", ref=ref),
        "blocked_claims": ["claim-action-1"],
        "safe_support_refs": [ref],
        "recommendation_draft": {
            "recommended_action": "issue_coupon",
            "reasoning_summary": f"Unsupported model reasoning {RAW_REASON_PAYLOAD}",
            "evidence_refs": [ref],
            "missing_info": [RAW_REASON_PAYLOAD, "verifier_prompt"],
        },
        "business_context": {
            "order": {"order_no": "ORD-1001", "status": "delivered", "item_name": "测试商品"},
        },
        "proposed_action": {"action_type": "coupon_grant"},
        "approval_result": {"decision": "approve"},
        "action_draft": {"draft_id": "draft-should-not-appear", "status": "draft_created"},
        "draft_outcome": {"status": "not_executed_demo", "draft_id": "draft-should-not-appear"},
    }

    result = await final_response(state)
    response_text = result["final_response"]

    assert "人工复核" in response_text
    assert "未创建审批请求或动作草稿" in response_text
    assert result["llm_outputs"]["final_response"]["final_status"] == "manual_review"
    assert "草稿已创建" not in response_text
    assert "draft-should-not-appear" not in response_text
    for unsafe in (RAW_REASON_PAYLOAD, VERIFIER_TRACE, PRIVATE_REASONING, "verifier_prompt", "private_reasoning"):
        assert unsafe not in response_text


@pytest.mark.asyncio
async def test_claim_verification_bundle_wins_over_legacy_verifier_fields(
    base_state: dict[str, Any],
) -> None:
    ref = _evidence_ref()
    state = {
        **base_state,
        "rag_context_status": "verified",
        "verified_evidence_package": _verified_package(status="verified", ref=ref),
        "claim_verification_bundle": _claim_bundle(
            route="manual_review",
            overall_status="blocked",
            ref=ref,
            reason_codes=["unsupported"],
        ),
        "blocked_claims": ["claim-action-1"],
        "verification_route": "allow",
        "verifier_status": "verified",
        "verifier_reason_codes": ["legacy_allow_should_not_win"],
        "rag_verification": _verification_state(outcome="verified", route="allow", reason_codes=[]),
        "recommendation_draft": {
            "recommended_action": "issue_coupon",
            "reasoning_summary": "Legacy verifier said allow, canonical bundle blocks it.",
            "evidence_refs": [ref],
            "missing_info": [],
        },
        "proposed_action": {"action_type": "coupon_grant"},
    }

    result = await final_response(state)
    output = result["llm_outputs"]["final_response"]

    assert output["final_status"] == "manual_review"
    assert output["verification_route"] == "manual_review"
    assert output["safe_projection_source"] == "claim_verification_bundle"
    assert output["verification_authoritative"] is True
    assert "legacy_allow_should_not_win" not in result["final_response"]
    assert "issue_coupon" not in result["final_response"]


@pytest.mark.asyncio
async def test_verified_evidence_package_wins_over_legacy_verifier_fields_when_claim_bundle_absent(
    base_state: dict[str, Any],
) -> None:
    state = {
        **base_state,
        "rag_context_status": "no_evidence",
        "verified_evidence_package": _verified_package(status="no_evidence", reason_codes=["no_evidence"]),
        "verification_route": "allow",
        "verifier_status": "verified",
        "verifier_reason_codes": ["legacy_allow_should_not_win"],
        "rag_verification": _verification_state(outcome="verified", route="allow", reason_codes=[]),
        "recommendation_draft": {
            "recommended_action": "issue_coupon",
            "reasoning_summary": "Legacy verifier said allow, canonical RAG package has no evidence.",
            "evidence_refs": [],
            "missing_info": [DEBUG_PROJECTION],
        },
        "proposed_action": {"action_type": "coupon_grant"},
    }

    result = await final_response(state)
    output = result["llm_outputs"]["final_response"]

    assert output["final_status"] == "insufficient_evidence"
    assert output["verification_route"] == "insufficient_evidence"
    assert output["safe_projection_source"] == "verified_evidence_package"
    assert output["verification_authoritative"] is True
    assert "legacy_allow_should_not_win" not in result["final_response"]
    assert DEBUG_PROJECTION not in result["final_response"]


@pytest.mark.asyncio
async def test_current_run_legacy_verifier_fields_without_canonical_projection_are_non_authoritative(
    base_state: dict[str, Any],
) -> None:
    state = {
        **base_state,
        "verification_route": "allow",
        "verifier_status": "verified",
        "verifier_reason_codes": ["legacy_allow_should_not_win"],
        "rag_verification": _verification_state(outcome="verified", route="allow", reason_codes=[]),
        "recommendation_draft": {
            "recommended_action": "issue_coupon",
            "reasoning_summary": "Legacy verifier fields are not current-run authority.",
            "evidence_refs": [],
            "missing_info": [],
        },
        "proposed_action": {"action_type": "coupon_grant"},
    }

    result = await final_response(state)
    output = result["llm_outputs"]["final_response"]

    assert output["final_status"] == "manual_review"
    assert output["verification_route"] == "manual_review"
    assert output["safe_projection_source"] == "missing_canonical_projection"
    assert output["verification_authoritative"] is False
    assert "legacy_allow_should_not_win" not in result["final_response"]
    assert "issue_coupon" not in result["final_response"]


@pytest.mark.asyncio
async def test_historical_legacy_verifier_fallback_requires_compatibility_trace_marker(
    base_state: dict[str, Any],
) -> None:
    state = {
        **base_state,
        "rag_verification": _verification_state(
            outcome="ambiguous",
            route="manual_review",
            reason_codes=["level2_partial_overlap_ambiguous"],
        ),
        "trace_steps": [{"node": "generate_recommendation", "status": "completed"}],
        "recommendation_draft": {
            "recommended_action": "manual_review",
            "reasoning_summary": "Historical trace used legacy verifier projection.",
            "evidence_refs": [],
            "missing_info": [],
        },
    }

    result = await final_response(state)
    output = result["llm_outputs"]["final_response"]

    assert output["final_status"] == "manual_review"
    assert output["verification_route"] == "manual_review"
    assert output["safe_projection_source"] == "historical_compatibility_projection"
    assert output["verification_authoritative"] is False


@pytest.mark.asyncio
async def test_manual_review_response_keeps_business_facts_and_safe_missing_info(
    base_state: dict[str, Any],
) -> None:
    """A verifier block should explain known order facts without trusting draft hallucinations."""
    state = _state(
        base_state,
        outcome="ambiguous",
        route="manual_review",
        reason_codes=["level2_partial_overlap_ambiguous"],
    )
    state.update(
        {
            "recommendation_draft": {
                "recommended_action": "manual_review",
                "reasoning_summary": "订单ORD-2024-001当前状态为已完成，建议直接关闭。",
                "evidence_refs": [],
                "missing_info": [
                    "Verification did not allow recommendation",
                    "退款原因",
                    "退款场景分类",
                ],
            },
            "business_context": {
                "facts": {
                    "order": {
                        "order_no": "ORD-2024-001",
                        "status": "pending",
                        "item_name": "蓝牙降噪耳机 Pro",
                        "amount": "599.00",
                        "currency": "CNY",
                        "relation_hints": {
                            "has_active_refund": True,
                            "has_open_ticket": True,
                        },
                    }
                }
            },
        }
    )

    result = await final_response(state)

    assert "当前查询结果" in result["final_response"]
    assert "ORD-2024-001" in result["final_response"]
    assert "状态 pending" in result["final_response"]
    assert "蓝牙降噪耳机 Pro" in result["final_response"]
    assert "存在关联退款" in result["final_response"]
    assert "存在未关闭工单" in result["final_response"]
    assert "人工复核" in result["final_response"]
    assert "未创建审批请求或动作草稿" in result["final_response"]
    assert "退款原因" in result["final_response"]
    assert "退款场景分类" in result["final_response"]
    assert "Verification did not allow recommendation" not in result["final_response"]
    assert "已完成" not in result["final_response"]
    assert "直接关闭" not in result["final_response"]
    assert result["llm_outputs"]["final_response"]["final_status"] == "manual_review"


@pytest.mark.asyncio
async def test_policy_qa_partial_overlap_manual_review_renders_cited_policy_answer(
    base_state: dict[str, Any],
) -> None:
    """policy_qa with strong evidence can answer a lexical partial-overlap verifier result without action success."""
    state = {
        **base_state,
        "primary_intent": "policy_qa",
        "current_intent": "policy_qa",
        "requested_operation": "advise",
        "retrieval_status": "strong_evidence",
        "rag_verification": _verification_state(
            outcome="ambiguous",
            route="manual_review",
            reason_codes=["level2_partial_overlap_ambiguous"],
        ),
        "trace_steps": [{"node": "generate_recommendation", "status": "completed"}],
        "retrieved_evidence": {
            "status": "strong_evidence",
            "evidence_refs": [
                {
                    "evidence_id": "refund_policy/refund_policy_000@v1",
                    "doc_key": "refund_policy",
                    "chunk_id": "refund_policy_000",
                    "title": "退款规则",
                    "section": "超时自动退款",
                    "score": 0.88,
                    "tenant_id": "tenant-should-not-expose",
                }
            ],
        },
        "recommendation_draft": {
            "recommended_action": "manual_review",
            "reasoning_summary": "商家收到退款申请后二十四小时内应响应；超过四十八小时仍未处理且证据满足规则的，平台可自动同意退款。",
            "evidence_refs": [
                {
                    "doc_key": "refund_policy",
                    "chunk_id": "refund_policy_000",
                    "title": "退款规则",
                    "section": "超时自动退款",
                    "raw_provider_payload": {"private": "do-not-expose"},
                }
            ],
            "confidence": 0.0,
            "risk_level": "low",
            "missing_info": ["Verification did not allow recommendation"],
            "citation_validation": {"is_valid": True},
        },
    }

    result = await final_response(state)

    assert "政策说明" in result["final_response"]
    assert "超过四十八小时" in result["final_response"]
    assert "根据 refund_policy / refund_policy_000" in result["final_response"]
    assert "暂不能创建审批请求或动作草稿" not in result["final_response"]
    assert result["llm_outputs"]["final_response"]["final_status"] == "completed"
    assert result["llm_outputs"]["final_response"]["verification_route"] == "manual_review"
    assert result["llm_outputs"]["final_response"]["safe_projection_source"] == "historical_compatibility_projection"
    assert result["llm_outputs"]["final_response"]["verification_authoritative"] is False
    assert result["llm_outputs"]["final_response"]["model_selected_route"] is False
    assert result["trace_steps"][-1]["evidence_refs"] == [
        {
            "evidence_id": "refund_policy/refund_policy_000@v1",
            "doc_key": "refund_policy",
            "chunk_id": "refund_policy_000",
            "title": "退款规则",
            "section": "超时自动退款",
            "score": 0.88,
        }
    ]


@pytest.mark.asyncio
async def test_policy_qa_partial_overlap_with_action_state_still_fails_closed(
    base_state: dict[str, Any],
) -> None:
    state = {
        **base_state,
        "primary_intent": "policy_qa",
        "current_intent": "policy_qa",
        "requested_operation": "advise",
        "retrieval_status": "strong_evidence",
        "rag_verification": _verification_state(
            outcome="ambiguous",
            route="manual_review",
            reason_codes=["level2_partial_overlap_ambiguous"],
        ),
        "trace_steps": [{"node": "generate_recommendation", "status": "completed"}],
        "recommendation_draft": {
            "recommended_action": "manual_review",
            "reasoning_summary": "商家超时未处理时平台可自动退款。",
            "evidence_refs": [
                {
                    "doc_key": "refund_policy",
                    "chunk_id": "refund_policy_000",
                    "title": "退款规则",
                    "section": "超时自动退款",
                }
            ],
            "confidence": 0.0,
            "risk_level": "low",
            "missing_info": ["Verification did not allow recommendation"],
            "citation_validation": {"is_valid": True},
        },
        "action_draft": {"draft_id": "draft-should-not-appear"},
    }

    result = await final_response(state)

    assert "人工复核" in result["final_response"]
    assert "draft-should-not-appear" not in result["final_response"]
    assert result["llm_outputs"]["final_response"]["final_status"] == "manual_review"
    assert "evidence_refs" not in result["trace_steps"][-1]


@pytest.mark.asyncio
async def test_final_response_trace_prefers_current_verified_package_over_stale_state_refs(
    base_state: dict[str, Any],
) -> None:
    current_ref = _evidence_ref()
    stale_ref = {
        **current_ref,
        "evidence_id": "stale-policy/stale-chunk@v1",
        "policy_version": "v1",
        "score": 0.11,
        "retrieval_config_version": "stale-config",
    }
    candidate_ref = {
        **current_ref,
        "evidence_id": "candidate-policy/candidate-chunk@v2",
        "policy_version": "v2",
        "score": 0.22,
        "retrieval_config_version": "candidate-config",
    }
    state = {
        **base_state,
        "rag_context_status": "verified",
        "verified_evidence_package": _verified_package(status="verified", ref=current_ref),
        "evidence_refs": [stale_ref],
        "retrieved_evidence": {"evidence_refs": [candidate_ref]},
        "recommendation_draft": {
            "recommended_action": "manual_review",
            "reasoning_summary": "Use the verified current policy.",
            "evidence_refs": [
                {
                    "doc_key": current_ref["doc_key"],
                    "chunk_id": current_ref["chunk_id"],
                    "title": "Refund policy",
                    "section": "Compensation",
                }
            ],
            "confidence": 0.91,
            "risk_level": "low",
            "missing_info": [],
            "citation_validation": {"is_valid": True},
        },
        "risk_assessment": {
            "risk_level": "low",
            "risk_reason": "Policy explanation only.",
            "approval_required": False,
            "rule_ref": "LR-01",
        },
    }

    result = await final_response(state)

    trace_refs = result["trace_steps"][-1]["evidence_refs"]
    assert [ref["evidence_id"] for ref in trace_refs] == [current_ref["evidence_id"]]
    assert trace_refs[0]["policy_version"] == current_ref["policy_version"]
    assert all(ref["evidence_id"] != stale_ref["evidence_id"] for ref in trace_refs)
    assert all(ref["evidence_id"] != candidate_ref["evidence_id"] for ref in trace_refs)
