from __future__ import annotations

import asyncio
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import CheckConstraint, ForeignKeyConstraint, Index, UniqueConstraint, text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from tests.migration_helpers import upgrade_to_head_with_evidence_cutover


MIGRATION_PATH = Path("src/db/migrations/versions/023_phase64_1_auto_action_capabilities.py")
DATABASE_URL = "postgresql+asyncpg://moca:moca_dev@localhost:5432/moca_test"
EXPECTED_COLUMNS = {
    "id",
    "schema_version",
    "key_version",
    "opaque_ref",
    "nonce",
    "tenant_id",
    "actor_id",
    "run_id",
    "merchant_scope_hash",
    "target_merchant_id",
    "canonical_action",
    "action_payload_hash",
    "safety_snapshot_ref",
    "safety_snapshot_hash",
    "risk_decision_ref",
    "risk_decision_hash",
    "risk_disposition",
    "handler",
    "issued_at",
    "expires_at",
    "status",
    "consumed_at",
    "resulting_draft_id",
    "idempotency_key",
}
EXPECTED_SCHEMA_ITEMS = {
    "uq_auto_action_capabilities_opaque_ref",
    "uq_auto_action_capabilities_nonce",
    "ck_auto_action_capabilities_status",
    "ck_auto_action_capabilities_expiry",
    "fk_auto_action_capabilities_tenant",
    "fk_auto_action_capabilities_actor",
    "fk_auto_action_capabilities_run",
    "fk_auto_action_capabilities_draft",
    "ix_auto_action_capabilities_tenant_run",
    "ix_auto_action_capabilities_status_expiry",
}


def _source() -> str:
    assert MIGRATION_PATH.exists()
    return MIGRATION_PATH.read_text(encoding="utf-8")


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


async def _schema_snapshot() -> tuple[set[str], set[str], set[str]]:
    engine = create_async_engine(DATABASE_URL, future=True, poolclass=NullPool)
    try:
        async with engine.connect() as conn:
            tables = {
                row[0]
                for row in await conn.execute(text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'"))
            }
            columns = {
                row[0]
                for row in await conn.execute(
                    text(
                        "SELECT column_name FROM information_schema.columns "
                        "WHERE table_schema = 'public' AND table_name = 'auto_action_capabilities'"
                    )
                )
            }
            schema_items = {
                row[0]
                for row in await conn.execute(
                    text(
                        "SELECT constraint_name FROM information_schema.table_constraints "
                        "WHERE table_schema = 'public' AND table_name = 'auto_action_capabilities' "
                        "UNION SELECT indexname FROM pg_indexes "
                        "WHERE schemaname = 'public' AND tablename = 'auto_action_capabilities'"
                    )
                )
            }
            return tables, columns, schema_items
    finally:
        await engine.dispose()


def test_capability_migration_declares_head_and_matching_orm_contract():
    source = _source()
    from src.db.models import AutoActionCapability, Base

    table = Base.metadata.tables[AutoActionCapability.__tablename__]
    item_types = (CheckConstraint, ForeignKeyConstraint, Index, UniqueConstraint)
    schema_items = {
        item.name for item in [*table.constraints, *table.indexes] if isinstance(item, item_types) and item.name
    }

    assert 'revision: str = "023_phase64_1_auto_action_capabilities"' in source
    assert 'down_revision: str | None = "022_case_working_context"' in source
    assert EXPECTED_COLUMNS == set(table.c.keys())
    assert EXPECTED_SCHEMA_ITEMS.issubset(schema_items)
    assert "auto_action_capabilities" in source
    assert 'op.drop_table("auto_action_capabilities")' in source


def test_capability_migration_upgrade_downgrade_reupgrade_round_trip():
    async def round_trip() -> None:
        await _reset_schema()
        cfg = _config()
        await asyncio.to_thread(command.upgrade, cfg, "023_phase64_1_auto_action_capabilities")
        tables, columns, schema_items = await _schema_snapshot()
        assert "auto_action_capabilities" in tables
        assert columns == EXPECTED_COLUMNS
        assert EXPECTED_SCHEMA_ITEMS.issubset(schema_items)

        await asyncio.to_thread(command.downgrade, cfg, "022_case_working_context")
        tables, columns, schema_items = await _schema_snapshot()
        assert "auto_action_capabilities" not in tables
        assert columns == set()
        assert schema_items == set()

        await asyncio.to_thread(command.upgrade, cfg, "023_phase64_1_auto_action_capabilities")
        tables, columns, schema_items = await _schema_snapshot()
        assert "auto_action_capabilities" in tables
        assert columns == EXPECTED_COLUMNS
        assert EXPECTED_SCHEMA_ITEMS.issubset(schema_items)

        await upgrade_to_head_with_evidence_cutover(cfg, database_url=DATABASE_URL)

    asyncio.run(round_trip())
