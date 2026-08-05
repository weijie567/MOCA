from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from scripts import eval_rag_hit_at_5 as legacy_eval
from scripts.eval_rag import (
    DEFAULT_GOLDEN_SET,
    DEFAULT_OUTPUT,
    DEFAULT_THRESHOLD,
    _build_report,
    _load_cases,
    _parser,
    _ranked_evidence,
    _score_case,
    _search_policy,
)
from src.api.schemas.search import EvidenceItem, RetrievalResult
from src.knowledge.retrieval import PolicyRetrievalHit


def _result(
    *,
    status: str = "strong_evidence",
    evidence: list[EvidenceItem] | None = None,
) -> RetrievalResult:
    items = evidence or []
    return RetrievalResult(
        query="测试问题",
        retrieval_status=status,
        evidence=items,
        best_score=max((item.score for item in items), default=0.0),
    )


def _evidence(
    *,
    doc_key: str = "refund_policy",
    chunk_id: str = "refund_policy_001",
    section: str = "七天无理由退货退款",
    score: float = 0.82,
    text: str = "消费者在签收商品后七个自然日内申请退货退款，且商品保持完好。",
    selected_by: list[str] | None = None,
    dense_rank: int | None = None,
    sparse_rank: int | None = None,
    fuzzy_rank: int | None = None,
    rrf_score: float | None = None,
) -> EvidenceItem:
    return EvidenceItem(
        doc_key=doc_key,
        chunk_id=chunk_id,
        title="退款规则",
        section=section,
        score=score,
        text=text,
        selected_by=selected_by,
        dense_rank=dense_rank,
        sparse_rank=sparse_rank,
        fuzzy_rank=fuzzy_rank,
        rrf_score=rrf_score,
    )


def test_score_case_hits_when_expected_chunk_is_in_top5():
    case = {
        "query": "七天无理由退款怎么处理？",
        "expected_doc_ids": ["refund_policy"],
        "expected_chunk_ids": ["refund_policy_001"],
        "should_fallback": False,
    }

    score = _score_case(case, _result(evidence=[_evidence()]))

    assert score["hit"] is True
    assert score["reason"] == "expected_chunk_in_top5"
    assert score["expected_doc_id_hit"] is True
    assert score["got_chunks"] == ["refund_policy_001"]


def test_score_case_doc_id_only_match_is_diagnostic_not_hit():
    case = {
        "query": "七天无理由退款怎么处理？",
        "expected_doc_ids": ["refund_policy"],
        "expected_chunk_ids": ["refund_policy_001"],
        "should_fallback": False,
    }

    score = _score_case(case, _result(evidence=[_evidence(chunk_id="refund_policy_002")]))

    assert score["hit"] is False
    assert score["reason"] == "expected_chunk_not_in_top5"
    assert score["expected_doc_id_hit"] is True
    assert score["got_chunks"] == ["refund_policy_002"]


def test_score_case_fallback_requires_no_evidence_status():
    case = {
        "query": "如何更换银行卡绑定手机号？",
        "expected_doc_ids": [],
        "expected_chunk_ids": [],
        "should_fallback": True,
    }

    hit = _score_case(case, _result(status="no_evidence"))
    miss = _score_case(case, _result(status="partial_evidence", evidence=[_evidence()]))

    assert hit["hit"] is True
    assert hit["reason"] == "fallback_no_evidence"
    assert miss["hit"] is False
    assert miss["reason"] == "should_fallback_but_got_results"


def test_ranked_evidence_preserves_retriever_order_and_text_snippets():
    rows = _ranked_evidence(
        _result(
            evidence=[
                _evidence(chunk_id="refund_policy_002", score=0.78, text="第二条证据"),
                _evidence(chunk_id="refund_policy_001", score=0.74, text="第一条证据"),
            ]
        )
    )

    assert rows == [
        {
            "rank": 1,
            "doc_key": "refund_policy",
            "chunk_id": "refund_policy_002",
            "section": "七天无理由退货退款",
            "score": 0.78,
            "text_snippet": "第二条证据",
        },
        {
            "rank": 2,
            "doc_key": "refund_policy",
            "chunk_id": "refund_policy_001",
            "section": "七天无理由退货退款",
            "score": 0.74,
            "text_snippet": "第一条证据",
        },
    ]


def test_ranked_evidence_includes_optional_hybrid_trace_without_business_facts():
    rows = _ranked_evidence(
        _result(
            evidence=[
                _evidence(
                    selected_by=["sparse", "fuzzy"],
                    sparse_rank=1,
                    fuzzy_rank=1,
                    rrf_score=0.0328,
                )
            ]
        )
    )

    assert rows[0]["selected_by"] == ["sparse", "fuzzy"]
    assert rows[0]["sparse_rank"] == 1
    assert rows[0]["fuzzy_rank"] == 1
    assert rows[0]["rrf_score"] == 0.0328
    assert "business_fact_refs" not in rows[0]
    assert "EvidenceRefV1" not in rows[0]


@pytest.mark.asyncio
async def test_search_policy_preserves_hybrid_trace_from_retrieval_hits():
    engine = SimpleNamespace(
        retrieve_hits=AsyncMock(
            return_value=(
                "strong_evidence",
                [
                    PolicyRetrievalHit(
                        doc_key="refund_policy",
                        chunk_id="refund_policy_001",
                        title="退款规则",
                        section="七天无理由退货退款",
                        policy_version="v1",
                        text="证据正文",
                        score=0.82,
                        rank=1,
                        selected_by=("dense", "sparse"),
                        dense_rank=1,
                        sparse_rank=2,
                        rrf_score=0.032,
                    )
                ],
                0.82,
            )
        )
    )

    result = await _search_policy(
        engine=engine,
        query="七天无理由退款怎么处理？",
        tenant_id=uuid4(),
        top_k=5,
    )

    engine.retrieve_hits.assert_awaited_once()
    assert result.retrieval_status == "strong_evidence"
    assert result.evidence[0].selected_by == ["dense", "sparse"]
    assert result.evidence[0].dense_rank == 1
    assert result.evidence[0].sparse_rank == 2
    assert result.evidence[0].rrf_score == 0.032
    assert _ranked_evidence(result)[0]["selected_by"] == ["dense", "sparse"]


def test_eval_parser_keeps_official_top5_and_allows_diagnostic_depth():
    default_args = _parser().parse_args([])
    diagnostic_args = _parser().parse_args(["--diagnostic-top-k", "20"])

    assert default_args.golden_set == DEFAULT_GOLDEN_SET
    assert default_args.output == DEFAULT_OUTPUT
    assert default_args.threshold == DEFAULT_THRESHOLD == 0.85
    assert default_args.diagnostic_top_k == 5
    assert diagnostic_args.diagnostic_top_k == 20


def test_report_uses_canonical_metrics_thresholds_and_status():
    report = _build_report(
        total_cases=4,
        hits=1,
        fallback_correct=1,
        fallback_total=1,
        threshold=DEFAULT_THRESHOLD,
        per_category={
            "fallback": {"total": 1, "hit": 1},
            "refund_rule": {"total": 3, "hit": 1},
        },
        failed_cases=[{"id": "miss-1"}],
    )

    assert report["eval_type"] == "rag"
    assert report["status"] == "fail"
    assert report["thresholds"] == {
        "hit_at_5": DEFAULT_THRESHOLD,
        "fallback_accuracy": DEFAULT_THRESHOLD,
    }
    assert report["metrics"] == {
        "hit_at_5": 1 / 3,
        "fallback_accuracy": 1.0,
        "total_cases": 4,
        "hit_cases": 1,
        "fallback_cases": 1,
        "fallback_correct": 1,
    }
    assert report["per_category"]["refund_rule"] == {"total": 3, "hit": 1, "rate": 1 / 3}
    assert report["failed_cases"] == [{"id": "miss-1"}]


def test_canonical_golden_set_has_current_22_case_schema():
    cases = _load_cases(DEFAULT_GOLDEN_SET)
    required_fields = {
        "query",
        "expected_doc_ids",
        "expected_chunk_ids",
        "category",
        "should_fallback",
    }

    assert len(cases) == 22
    assert all(required_fields <= case.keys() for case in cases)
    assert all(isinstance(case["expected_doc_ids"], list) for case in cases)
    assert all(isinstance(case["expected_chunk_ids"], list) for case in cases)
    assert len([case for case in cases if case.get("phase") == "23"]) == 8


def test_active_entrypoints_import_canonical_evaluator():
    makefile = Path("Makefile").read_text(encoding="utf-8")
    eval_all_source = Path("scripts/eval_all.py").read_text(encoding="utf-8")
    eval_all_tree = ast.parse(eval_all_source)
    imported_names = {
        alias.name
        for node in ast.walk(eval_all_tree)
        if isinstance(node, ast.ImportFrom) and node.module == "scripts.eval_rag"
        for alias in node.names
    }

    assert "eval-rag:\n\tuv run python scripts/eval_rag.py" in makefile
    assert {"DEFAULT_THRESHOLD", "run_rag_eval"} <= imported_names
    assert "scripts.eval_rag_hit_at_5" not in eval_all_source


def test_legacy_module_delegates_to_canonical_evaluator():
    assert legacy_eval.DEFAULT_GOLDEN_SET == DEFAULT_GOLDEN_SET
    assert legacy_eval.DEFAULT_OUTPUT == DEFAULT_OUTPUT
    assert legacy_eval.DEFAULT_THRESHOLD == DEFAULT_THRESHOLD
    assert legacy_eval._parser is _parser
    assert legacy_eval._ranked_evidence is _ranked_evidence
    assert legacy_eval._score_case is _score_case
