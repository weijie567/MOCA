"""Shared staged-migration helpers for tests that upgrade through Phase 64.2."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from alembic import command
from alembic.config import Config
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from src.db.models import EvidenceIdentityRollout
from src.repositories.evidence_version_repo import EvidenceVersionRepository


async def upgrade_to_head_with_evidence_cutover(
    config: Config,
    *,
    database_url: str,
    target_revision: str = "head",
) -> None:
    """Cross 025→026 only after the production CAS/health activation owner runs."""

    await asyncio.to_thread(command.upgrade, config, "025_phase64_2_immutable_evidence")
    engine = create_async_engine(database_url, future=True, poolclass=NullPool)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with session_factory() as session:
            rollout = await session.get(EvidenceIdentityRollout, 1)
            assert rollout is not None
            assert (
                rollout.rollout_version,
                rollout.dual_write_enabled_at,
                rollout.backfill_watermark_sequence,
                rollout.reconciled_through_sequence,
                rollout.canonical_reads_enabled,
                rollout.quarantine_reason,
            ) == (0, None, None, None, False, None)

            activated = await EvidenceVersionRepository(session).activate_dual_write(
                expected_rollout_version=0,
                health_checked_at=datetime.now(UTC),
            )
            await session.commit()
            assert activated.rollout_version == 1
            assert activated.dual_write_enabled_at is not None
            assert activated.audit_counts_json["dual_write_health"] == "healthy"
    finally:
        await engine.dispose()

    await asyncio.to_thread(command.upgrade, config, target_revision)
