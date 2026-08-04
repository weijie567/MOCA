from __future__ import annotations

import asyncio
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import CheckConstraint, ForeignKeyConstraint, Index, text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool


MIGRATION_PATH = Path("src/db/migrations/versions/024_phase64_1_resume_attempt_lease.py")
DATABASE_URL = "postgresql+asyncpg://moca:moca_dev@localhost:5432/moca_test"
EXPECTED_COLUMNS = {
    "resume_attempt_id",
    "resume_attempt_decision_id",
    "resume_attempt_status",
    "resume_lease_expires_at",
    "resume_attempt_started_at",
    "resume_attempt_updated_at",
}
EXPECTED_SCHEMA_ITEMS = {
    "fk_approval_requests_resume_attempt_decision",
    "ck_approval_requests_resume_attempt_status",
    "ck_approval_requests_resume_attempt_identity",
    "ck_approval_requests_resume_attempt_lease",
    "ix_approval_requests_resume_attempt",
}


def _config() -> Config:
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", DATABASE_URL)
    cfg.attributes["database_url"] = DATABASE_URL
    return cfg


async def _reset_schema() -> None:
    engine = create_async_engine(DATABASE_URL, future=True, poolclass=NullPool)
    try:
        async with engine.begin() as conn:
            await conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
            await conn.execute(text("CREATE SCHEMA public"))
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
    finally:
        await engine.dispose()


async def _schema_snapshot() -> tuple[set[str], set[str]]:
    engine = create_async_engine(DATABASE_URL, future=True, poolclass=NullPool)
    try:
        async with engine.connect() as conn:
            columns = {
                row[0]
                for row in await conn.execute(
                    text(
                        "SELECT column_name FROM information_schema.columns "
                        "WHERE table_schema = 'public' AND table_name = 'approval_requests'"
                    )
                )
                if row[0] in EXPECTED_COLUMNS
            }
            schema_items = {
                row[0]
                for row in await conn.execute(
                    text(
                        "SELECT constraint_name FROM information_schema.table_constraints "
                        "WHERE table_schema = 'public' AND table_name = 'approval_requests' "
                        "UNION SELECT indexname FROM pg_indexes "
                        "WHERE schemaname = 'public' AND tablename = 'approval_requests'"
                    )
                )
                if row[0] in EXPECTED_SCHEMA_ITEMS
            }
            return columns, schema_items
    finally:
        await engine.dispose()


def test_resume_attempt_migration_matches_orm_contract() -> None:
    source = MIGRATION_PATH.read_text(encoding="utf-8")
    from src.db.models import ApprovalRequest, Base

    table = Base.metadata.tables[ApprovalRequest.__tablename__]
    item_types = (CheckConstraint, ForeignKeyConstraint, Index)
    schema_items = {
        item.name for item in [*table.constraints, *table.indexes] if isinstance(item, item_types) and item.name
    }

    assert 'revision: str = "024_phase64_1_resume_attempt_lease"' in source
    assert 'down_revision: str | None = "023_phase64_1_auto_action_capabilities"' in source
    assert EXPECTED_COLUMNS.issubset(table.c.keys())
    assert EXPECTED_SCHEMA_ITEMS.issubset(schema_items)


def test_resume_attempt_migration_upgrade_downgrade_reupgrade_round_trip() -> None:
    async def round_trip() -> None:
        await _reset_schema()
        cfg = _config()
        await asyncio.to_thread(command.upgrade, cfg, "head")
        columns, schema_items = await _schema_snapshot()
        assert columns == EXPECTED_COLUMNS
        assert schema_items == EXPECTED_SCHEMA_ITEMS

        await asyncio.to_thread(command.downgrade, cfg, "023_phase64_1_auto_action_capabilities")
        columns, schema_items = await _schema_snapshot()
        assert columns == set()
        assert schema_items == set()

        await asyncio.to_thread(command.upgrade, cfg, "head")
        columns, schema_items = await _schema_snapshot()
        assert columns == EXPECTED_COLUMNS
        assert schema_items == EXPECTED_SCHEMA_ITEMS

    asyncio.run(round_trip())
