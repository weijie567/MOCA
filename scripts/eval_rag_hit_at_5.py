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
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Tenant
from src.db.session import SessionLocal
from src.rag.embedder import EmbeddingService
from src.rag.retriever import Retriever
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
    return parser


def _load_cases(path: str) -> list[dict[str, Any]]:
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def _record_category(per_category: dict[str, dict[str, int]], category: str, hit: bool) -> None:
    if category not in per_category:
        per_category[category] = {"total": 0, "hit": 0}
    per_category[category]["total"] += 1
    if hit:
        per_category[category]["hit"] += 1


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
            if "expected" in failed:
                print(f"    expected: {failed['expected']}")
                print(f"    got:      {failed['got']}")
            if "missing_expected_chunks" in failed:
                print(f"    missing expected chunks: {failed['missing_expected_chunks']}")


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

        retriever = Retriever(
            chunk_repo=PolicyChunkRepository(session),
            embedder=EmbeddingService(),
        )

        hits = 0
        fallback_correct = 0
        fallback_total = 0
        failed_cases: list[dict[str, Any]] = []
        per_category: dict[str, dict[str, int]] = {}

        for case in cases:
            result = await retriever.search(query=case["query"], tenant_id=tenant_id, top_k=5)
            retrieved_ids = {evidence.chunk_id for evidence in result.evidence}
            category = case["category"]

            if case.get("should_fallback"):
                fallback_total += 1
                hit = result.retrieval_status == "no_evidence"
                if hit:
                    fallback_correct += 1
                else:
                    failed_cases.append(
                        {
                            "query": case["query"][:60],
                            "reason": "should_fallback_but_got_results",
                            "got_status": result.retrieval_status,
                            "got_chunks": sorted(retrieved_ids)[:5],
                        }
                    )
                _record_category(per_category, category, hit)
                continue

            expected = set(case["expected_chunk_ids"])
            matched = bool(expected & retrieved_ids)
            if matched:
                hits += 1
            else:
                failed_cases.append(
                    {
                        "query": case["query"][:60],
                        "reason": "expected_chunk_not_in_top5",
                        "expected": sorted(expected),
                        "got": sorted(retrieved_ids),
                        "missing_expected_chunks": sorted(expected - retrieved_ids),
                    }
                )
            _record_category(per_category, category, matched)

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
