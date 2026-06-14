"""RAG evaluation script.

Usage:
    uv run python scripts/eval_rag.py
    uv run python scripts/eval_rag.py --golden-set evaluation/golden/rag_cases.jsonl
    uv run python scripts/eval_rag.py --threshold 0.85
    uv run python scripts/eval_rag.py --tenant-id <uuid>

Requires a running PostgreSQL database with ingested policy documents.
Exits non-zero if Hit@5 or fallback accuracy is below the threshold.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Tenant
from src.db.session import SessionLocal
from src.knowledge.retrieval import POLICY_NO_EVIDENCE_MESSAGE, PolicyRetrievalEngine
from src.knowledge.schemas import KnowledgeContext
from src.rag.embedder import EmbeddingService
from src.rag.schemas import EvidenceItem, RetrievalResult
from src.repositories.policy_chunk_repo import PolicyChunkRepository


DEFAULT_GOLDEN_SET = "evaluation/golden/rag_cases.jsonl"
DEFAULT_OUTPUT = "evaluation/reports/rag_eval.json"
DEFAULT_THRESHOLD = 0.85


async def resolve_tenant_id(session: AsyncSession, tenant_id_str: str | None) -> UUID:
    """Resolve tenant UUID from --tenant-id or use the first active tenant in the DB."""
    if tenant_id_str:
        return UUID(tenant_id_str)

    stmt = select(Tenant).where(Tenant.status == "active").order_by(Tenant.created_at.asc()).limit(1)
    tenant = (await session.execute(stmt)).scalar_one_or_none()
    if tenant is None:
        raise RuntimeError("No active tenants in database. Run scripts/seed_demo.py first or pass --tenant-id.")
    return tenant.id


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="RAG Hit@5 Evaluation")
    parser.add_argument("--golden-set", default=DEFAULT_GOLDEN_SET, help="Path to JSONL golden set")
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD, help="Minimum accepted score")
    parser.add_argument("--tenant-id", help="Tenant UUID (default: first active tenant)")
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help="Path to write JSON report")
    parser.add_argument(
        "--diagnostic-top-k",
        type=int,
        default=5,
        help="Diagnostic-only evidence depth for failed cases; official scoring remains top_k=5",
    )
    return parser


def _load_cases(path: str) -> list[dict[str, Any]]:
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def _record_category(per_category: dict[str, dict[str, int]], category: str, hit: bool) -> None:
    if category not in per_category:
        per_category[category] = {"total": 0, "hit": 0}
    per_category[category]["total"] += 1
    if hit:
        per_category[category]["hit"] += 1


def _ranked_evidence(result: RetrievalResult) -> list[dict[str, object]]:
    return [
        {
            "rank": rank,
            "doc_key": evidence.doc_key,
            "chunk_id": evidence.chunk_id,
            "section": evidence.section,
            "score": evidence.score,
            "text_snippet": evidence.text,
        }
        for rank, evidence in enumerate(result.evidence, start=1)
    ]


def _score_case(case: dict[str, Any], result: RetrievalResult) -> dict[str, Any]:
    expected_chunks = list(case.get("expected_chunk_ids", []))
    expected_docs = set(case.get("expected_doc_ids", []))
    got_chunks = [evidence.chunk_id for evidence in result.evidence]
    got_docs = {evidence.doc_key for evidence in result.evidence}
    expected_doc_id_hit = bool(expected_docs & got_docs)
    ranked_evidence = _ranked_evidence(result)

    if case.get("should_fallback"):
        hit = result.retrieval_status == "no_evidence"
        reason = "fallback_no_evidence" if hit else "should_fallback_but_got_results"
    else:
        hit = bool(set(expected_chunks) & set(got_chunks))
        reason = "expected_chunk_in_top5" if hit else "expected_chunk_not_in_top5"

    return {
        "hit": hit,
        "reason": reason,
        "expected_chunks": expected_chunks,
        "got_chunks": got_chunks,
        "expected_doc_id_hit": expected_doc_id_hit,
        "ranked_evidence": ranked_evidence,
        "retrieval_status": result.retrieval_status,
        "missing_expected_chunks": sorted(set(expected_chunks) - set(got_chunks)),
    }


async def _search_policy(
    *,
    engine: PolicyRetrievalEngine,
    query: str,
    tenant_id: UUID,
    top_k: int,
) -> RetrievalResult:
    status, hits, best_score = await engine.retrieve_hits(
        query=query,
        context=KnowledgeContext(
            tenant_id=str(tenant_id),
            user_id="rag-eval",
            role="evaluator",
            merchant_scope=["*"],
            run_id="rag-eval",
            trace_id="rag-eval",
            effective_at=datetime.now(UTC).isoformat(),
        ),
        max_results=top_k,
    )
    retrieval_status = status if status != "error" else "no_evidence"
    return RetrievalResult(
        query=query,
        retrieval_status=retrieval_status,
        evidence=[
            EvidenceItem(
                doc_key=hit.doc_key,
                chunk_id=hit.chunk_id,
                title=hit.title,
                section=hit.section,
                score=hit.score,
                text=hit.text[:300],
            )
            for hit in hits
        ],
        best_score=best_score,
        fallback_message=POLICY_NO_EVIDENCE_MESSAGE if retrieval_status == "no_evidence" else None,
    )


def _finalize_category_rates(per_category: dict[str, dict[str, int]]) -> dict[str, dict[str, float | int]]:
    return {
        category: {
            "total": stats["total"],
            "hit": stats["hit"],
            "rate": stats["hit"] / stats["total"] if stats["total"] else 0.0,
        }
        for category, stats in sorted(per_category.items())
    }


def _build_report(
    *,
    total_cases: int,
    hits: int,
    fallback_correct: int,
    fallback_total: int,
    threshold: float,
    per_category: dict[str, dict[str, int]],
    failed_cases: list[dict[str, Any]],
) -> dict[str, Any]:
    non_fallback = total_cases - fallback_total
    hit_at_5 = hits / non_fallback if non_fallback else 0.0
    fallback_acc = fallback_correct / fallback_total if fallback_total else 1.0
    status = "pass" if hit_at_5 >= threshold and fallback_acc >= threshold else "fail"

    return {
        "eval_type": "rag",
        "generated_at": datetime.now(UTC).isoformat(),
        "status": status,
        "thresholds": {"hit_at_5": threshold, "fallback_accuracy": threshold},
        "metrics": {
            "hit_at_5": hit_at_5,
            "fallback_accuracy": fallback_acc,
            "total_cases": total_cases,
            "hit_cases": hits,
            "fallback_cases": fallback_total,
            "fallback_correct": fallback_correct,
        },
        "per_category": _finalize_category_rates(per_category),
        "failed_cases": failed_cases,
    }


def _print_report(report: dict[str, Any]) -> None:
    metrics = report["metrics"]
    threshold = report["thresholds"]["hit_at_5"]

    print(f"\n{'=' * 60}")
    print("RAG Evaluation Report")
    print(f"{'=' * 60}")
    print(f"Total queries: {metrics['total_cases']}")
    print(f"Hit@5: {metrics['hit_at_5']:.1%} (threshold: {threshold:.0%})")
    print(f"Fallback accuracy: {metrics['fallback_accuracy']:.1%} (threshold: {threshold:.0%})")
    print("\nPer-category:")
    for category, stats in sorted(report["per_category"].items()):
        print(f"  {category}: {stats['rate']:.0%} ({stats['hit']}/{stats['total']})")

    if report["failed_cases"]:
        print(f"\nFailed cases ({len(report['failed_cases'])}):")
        for failed in report["failed_cases"]:
            print(f"  - {failed['query']}... | {failed['reason']}")
            print(f"    retrieval_status: {failed['retrieval_status']}")
            print(f"    expected_doc_id_hit: {failed['expected_doc_id_hit']}")
            if "expected_chunks" in failed:
                print(f"    expected chunks: {failed['expected_chunks']}")
                print(f"    got chunks:      {failed['got_chunks']}")
            if "missing_expected_chunks" in failed:
                print(f"    missing expected chunks: {failed['missing_expected_chunks']}")
            print("    ranked evidence:")
            for evidence in failed["ranked_evidence"]:
                print(
                    "      "
                    f"rank={evidence['rank']} "
                    f"doc_key={evidence['doc_key']} "
                    f"chunk_id={evidence['chunk_id']} "
                    f"section={evidence['section']} "
                    f"score={evidence['score']:.4f} "
                    f"text_snippet={evidence['text_snippet']}"
                )
            diagnostic_evidence = failed.get("diagnostic_ranked_evidence", [])
            if diagnostic_evidence:
                print("    diagnostic ranked evidence:")
                for evidence in diagnostic_evidence:
                    print(
                        "      "
                        f"rank={evidence['rank']} "
                        f"doc_key={evidence['doc_key']} "
                        f"chunk_id={evidence['chunk_id']} "
                        f"section={evidence['section']} "
                        f"score={evidence['score']:.4f} "
                        f"text_snippet={evidence['text_snippet']}"
                    )


async def run_rag_eval(
    golden_set_path: str | None = None,
    threshold: float = DEFAULT_THRESHOLD,
    tenant_id: str | None = None,
    diagnostic_top_k: int = 5,
) -> dict[str, Any]:
    """Run DB-backed RAG evaluation and return the JSON report dict."""
    cases = _load_cases(golden_set_path or DEFAULT_GOLDEN_SET)

    async with SessionLocal() as session:
        tenant_uuid = await resolve_tenant_id(session, tenant_id)
        engine = PolicyRetrievalEngine(
            chunk_repo=PolicyChunkRepository(session),
            embedder=EmbeddingService(),
        )

        hits = 0
        fallback_correct = 0
        fallback_total = 0
        failed_cases: list[dict[str, Any]] = []
        per_category: dict[str, dict[str, int]] = {}

        for case in cases:
            result = await _search_policy(engine=engine, query=case["query"], tenant_id=tenant_uuid, top_k=5)
            scored = _score_case(case, result)
            category = case["category"]

            if diagnostic_top_k != 5 and not scored["hit"]:
                diagnostic_result = await _search_policy(
                    engine=engine,
                    query=case["query"],
                    tenant_id=tenant_uuid,
                    top_k=diagnostic_top_k,
                )
                scored["diagnostic_ranked_evidence"] = _ranked_evidence(diagnostic_result)

            if case.get("should_fallback"):
                fallback_total += 1
                if scored["hit"]:
                    fallback_correct += 1
                else:
                    failed_cases.append(
                        {
                            "id": case.get("id", case["query"][:30]),
                            "query": case["query"][:60],
                            "category": category,
                            **scored,
                        }
                    )
                _record_category(per_category, category, scored["hit"])
                continue

            if scored["hit"]:
                hits += 1
            else:
                failed_cases.append(
                    {
                        "id": case.get("id", case["query"][:30]),
                        "query": case["query"][:60],
                        "category": category,
                        **scored,
                    }
                )
            _record_category(per_category, category, scored["hit"])

    return _build_report(
        total_cases=len(cases),
        hits=hits,
        fallback_correct=fallback_correct,
        fallback_total=fallback_total,
        threshold=threshold,
        per_category=per_category,
        failed_cases=failed_cases,
    )


async def main() -> None:
    parser = _parser()
    args = parser.parse_args()

    try:
        report = await run_rag_eval(
            golden_set_path=args.golden_set,
            threshold=args.threshold,
            tenant_id=args.tenant_id,
            diagnostic_top_k=args.diagnostic_top_k,
        )
    except FileNotFoundError:
        parser.error(f"golden set not found: {args.golden_set}")
    except json.JSONDecodeError as exc:
        parser.error(f"invalid JSONL in {args.golden_set}: {exc}")
    except ValueError:
        parser.error("--tenant-id must be a valid UUID")
    except RuntimeError as exc:
        parser.error(str(exc))

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    _print_report(report)

    if report["status"] == "fail":
        print(f"\nFAIL: Below threshold. JSON report written to {output_path}")
        sys.exit(1)

    print(f"\nPASS. JSON report written to {output_path}")
    sys.exit(0)


if __name__ == "__main__":
    asyncio.run(main())
