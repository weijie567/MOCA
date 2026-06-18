"""Rebuild retrieval-only policy chunk search_text for existing rows."""

from __future__ import annotations

import argparse
import asyncio
from uuid import UUID

from src.db.session import SessionLocal
from src.rag.search_text_backfill import rebuild_policy_chunk_search_texts


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Rebuild policy chunk search_text")
    parser.add_argument("--tenant-id", help="Optional tenant UUID to limit the rebuild")
    return parser


async def main() -> None:
    args = _parser().parse_args()
    tenant_id = UUID(args.tenant_id) if args.tenant_id else None
    async with SessionLocal() as session:
        count = await rebuild_policy_chunk_search_texts(session, tenant_id=tenant_id)
        await session.commit()
    print(f"Rebuilt search_text for {count} policy chunks.")


if __name__ == "__main__":
    asyncio.run(main())
