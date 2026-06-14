"""RAG Hit@5 evaluation script.

Usage:
    uv run python scripts/eval_rag_hit_at_5.py
    uv run python scripts/eval_rag_hit_at_5.py --golden-set eval/golden_rag_queries.jsonl
    uv run python scripts/eval_rag_hit_at_5.py --threshold 0.8
    uv run python scripts/eval_rag_hit_at_5.py --tenant-id <uuid>

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


DEFAULT_GOLDEN_SET = "eval/golden_rag_queries.jsonl"
DEFAULT_THRESHOLD = 0.80


async def resolve_tenant_id(session: AsyncSession, tenant_id_str: str | None) -> UUID:
    """Resolve tenant UUID from --tenant-id or use the first active tenant in the DB."""
    if tenant_id_str:
        return UUID(tenant_id_str)

    stmt = select(Tenant).where(Tenant.status == "active").order_by(Tenant.created_at.asc()).limit(1)
    tenant = (await session.execute(stmt)).scalar_one_or_none()
    if tenant is None:
        print("ERROR: No active tenants in database. Run scripts/seed_demo.py first or pass --tenant-id.")
        sys.exit(1)
    return tenant.id


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="RAG Hit@5 Evaluation")
    parser.add_argument("--golden-set", default=DEFAULT_GOLDEN_SET, help="Path to JSONL golden set")
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD, help="Minimum accepted score")
    parser.add_argument("--tenant-id", help="Tenant UUID (default: first active tenant)")
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


def _print_report(
    total_cases: int,
    hit_at_5: float,
    fallback_acc: float,
    threshold: float,
    per_category: dict[str, dict[str, int]],
    failed_cases: list[dict[str, Any]],
) -> None:
    print(f"\n{'=' * 60}")
    print("RAG Evaluation Report")
    print(f"{'=' * 60}")
    print(f"Total queries: {total_cases}")
    print(f"Hit@5: {hit_at_5:.1%} (threshold: {threshold:.0%})")
    print(f"Fallback accuracy: {fallback_acc:.1%} (threshold: {threshold:.0%})")
    print("\nPer-category:")
    for category, stats in sorted(per_category.items()):
        rate = stats["hit"] / stats["total"] if stats["total"] else 0
        print(f"  {category}: {rate:.0%} ({stats['hit']}/{stats['total']})")

    if failed_cases:
        print(f"\nFailed cases ({len(failed_cases)}):")
        for failed in failed_cases:
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


async def main() -> None:
    parser = _parser()
    args = parser.parse_args()

    try:
        cases = _load_cases(args.golden_set)
    except FileNotFoundError:
        parser.error(f"golden set not found: {args.golden_set}")
    except json.JSONDecodeError as exc:
        parser.error(f"invalid JSONL in {args.golden_set}: {exc}")

    async with SessionLocal() as session:
        try:
            tenant_id = await resolve_tenant_id(session, args.tenant_id)
        except ValueError:
            parser.error("--tenant-id must be a valid UUID")

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
            result = await _search_policy(engine=engine, query=case["query"], tenant_id=tenant_id, top_k=5)
            scored = _score_case(case, result)
            category = case["category"]

            if args.diagnostic_top_k != 5 and not scored["hit"]:
                diagnostic_result = await _search_policy(
                    engine=engine,
                    query=case["query"],
                    tenant_id=tenant_id,
                    top_k=args.diagnostic_top_k,
                )
                scored["diagnostic_ranked_evidence"] = _ranked_evidence(diagnostic_result)

            if case.get("should_fallback"):
                fallback_total += 1
                if scored["hit"]:
                    fallback_correct += 1
                else:
                    failed_cases.append({"query": case["query"][:60], **scored})
                _record_category(per_category, category, scored["hit"])
                continue

            if scored["hit"]:
                hits += 1
            else:
                failed_cases.append({"query": case["query"][:60], **scored})
            _record_category(per_category, category, scored["hit"])

    non_fallback = len(cases) - fallback_total
    hit_at_5 = hits / non_fallback if non_fallback else 0.0
    fallback_acc = fallback_correct / fallback_total if fallback_total else 1.0

    _print_report(len(cases), hit_at_5, fallback_acc, args.threshold, per_category, failed_cases)

    if hit_at_5 < args.threshold or fallback_acc < args.threshold:
        print("\nFAIL: Below threshold")
        sys.exit(1)

    print("\nPASS")
    sys.exit(0)


if __name__ == "__main__":
    asyncio.run(main())
