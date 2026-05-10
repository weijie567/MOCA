from __future__ import annotations

from scripts.eval_rag_hit_at_5 import _parser, _ranked_evidence, _score_case
from src.rag.schemas import EvidenceItem, RetrievalResult


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
) -> EvidenceItem:
    return EvidenceItem(
        doc_key=doc_key,
        chunk_id=chunk_id,
        title="退款规则",
        section=section,
        score=score,
        text=text,
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


def test_eval_parser_keeps_official_top5_and_allows_diagnostic_depth():
    default_args = _parser().parse_args([])
    diagnostic_args = _parser().parse_args(["--diagnostic-top-k", "20"])

    assert default_args.threshold == 0.80
    assert default_args.diagnostic_top_k == 5
    assert diagnostic_args.diagnostic_top_k == 20
