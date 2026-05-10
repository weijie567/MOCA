"""CLI script to ingest policy documents into pgvector.

Usage:
    uv run python scripts/ingest_policies.py
    uv run python scripts/ingest_policies.py --dir data/policies/
    uv run python scripts/ingest_policies.py --dry-run
    uv run python scripts/ingest_policies.py --tenant-id <uuid>
"""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
from uuid import UUID

from sqlalchemy import select

from src.db.models import Tenant
from src.db.session import SessionLocal
from src.rag.chunker import chunk_markdown
from src.rag.embedder import EmbeddingService
from src.rag.ingestion import IngestionReport, IngestionService


DOCUMENT_MANIFEST = [
    {"file": "refund_policy.md", "doc_key": "refund_policy", "doc_type": "refund_rule", "risk_level": "high", "title": "退款规则"},
    {"file": "refund_sop.md", "doc_key": "refund_sop", "doc_type": "sop", "risk_level": "medium", "title": "退款处理SOP"},
    {"file": "compensation_rules.md", "doc_key": "compensation_rules", "doc_type": "refund_rule", "risk_level": "high", "title": "补偿规则"},
    {"file": "merchant_faq.md", "doc_key": "merchant_faq", "doc_type": "faq", "risk_level": "low", "title": "商家FAQ"},
    {"file": "return_shipping.md", "doc_key": "return_shipping", "doc_type": "refund_rule", "risk_level": "medium", "title": "退货物流规则"},
    {"file": "quality_issue_policy.md", "doc_key": "quality_issue_policy", "doc_type": "refund_rule", "risk_level": "high", "title": "质量问题退款细则"},
    {"file": "partial_refund_rules.md", "doc_key": "partial_refund_rules", "doc_type": "refund_rule", "risk_level": "medium", "title": "部分退款规则"},
    {"file": "refund_time_limits.md", "doc_key": "refund_time_limits", "doc_type": "refund_rule", "risk_level": "medium", "title": "退款时效规则"},
    {"file": "high_value_refund.md", "doc_key": "high_value_refund", "doc_type": "refund_rule", "risk_level": "high", "title": "高价值订单退款规则"},
    {"file": "cross_border_refund.md", "doc_key": "cross_border_refund", "doc_type": "refund_rule", "risk_level": "medium", "title": "跨境订单退款规则"},
    {"file": "digital_goods_refund.md", "doc_key": "digital_goods_refund", "doc_type": "refund_rule", "risk_level": "low", "title": "虚拟商品退款规则"},
    {"file": "bulk_order_refund.md", "doc_key": "bulk_order_refund", "doc_type": "refund_rule", "risk_level": "medium", "title": "批量订单退款规则"},
    {"file": "customer_escalation_sop.md", "doc_key": "customer_escalation_sop", "doc_type": "sop", "risk_level": "medium", "title": "客户投诉升级SOP"},
    {"file": "compensation_approval_sop.md", "doc_key": "compensation_approval_sop", "doc_type": "sop", "risk_level": "high", "title": "补偿审批SOP"},
    {"file": "merchant_dispute_faq.md", "doc_key": "merchant_dispute_faq", "doc_type": "faq", "risk_level": "low", "title": "商家争议FAQ"},
]


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Ingest policy documents into pgvector")
    parser.add_argument("--dir", default="data/policies/", help="Policy documents directory")
    parser.add_argument("--dry-run", action="store_true", help="Parse and chunk only, no embedding/DB")
    parser.add_argument("--tenant-id", help="Tenant UUID (default: first tenant from DB)")
    return parser


def _print_reports(reports: list[IngestionReport]) -> None:
    print(f"{'doc_key':<30} {'status':<8} {'chunks':<6} error")
    print("-" * 72)
    for report in reports:
        print(f"{report.doc_key:<30} {report.status:<8} {report.chunks_created:<6} {report.error or ''}")


def _dry_run(dir_path: Path) -> list[IngestionReport]:
    reports: list[IngestionReport] = []
    for doc_meta in DOCUMENT_MANIFEST:
        doc_key = doc_meta["doc_key"]
        title = doc_meta["title"]
        try:
            content = (dir_path / doc_meta["file"]).read_text(encoding="utf-8")
            chunks = chunk_markdown(content, doc_key=doc_key)
            if not chunks:
                reports.append(IngestionReport(doc_key=doc_key, title=title, status="failed", error="No chunks produced"))
            else:
                reports.append(IngestionReport(doc_key=doc_key, title=title, status="success", chunks_created=len(chunks)))
        except Exception as exc:
            reports.append(IngestionReport(doc_key=doc_key, title=title, status="failed", error=str(exc)))
    return reports


async def _resolve_tenant_id(tenant_id_arg: str | None) -> UUID:
    if tenant_id_arg:
        return UUID(tenant_id_arg)

    async with SessionLocal() as session:
        stmt = select(Tenant).where(Tenant.status == "active").order_by(Tenant.created_at.asc()).limit(1)
        tenant = (await session.execute(stmt)).scalar_one_or_none()
        if tenant is None:
            raise RuntimeError("No active tenant found. Provide --tenant-id or seed demo data first.")
        return tenant.id


async def main() -> int:
    parser = _parser()
    args = parser.parse_args()
    dir_path = Path(args.dir)

    if args.dry_run:
        reports = _dry_run(dir_path)
        _print_reports(reports)
        return 1 if any(report.status != "success" for report in reports) else 0

    try:
        tenant_id = await _resolve_tenant_id(args.tenant_id)
    except ValueError:
        parser.error("--tenant-id must be a valid UUID")
    except Exception as exc:
        print(f"Failed to resolve tenant: {exc}")
        return 1

    async with SessionLocal() as session:
        service = IngestionService(session=session, embedder=EmbeddingService(), tenant_id=tenant_id)
        reports = await service.ingest_directory(dir_path, DOCUMENT_MANIFEST)

    _print_reports(reports)
    return 1 if any(report.status != "success" for report in reports) else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
