from __future__ import annotations

import asyncio
import ast
import uuid
from datetime import UTC, datetime
from pathlib import Path

import asyncpg
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import CheckConstraint, text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from src.db.models import Base
from src.memory.policy import MemoryPolicyDecision
from tests.conftest import TEST_DATABASE_URL, _ensure_test_database


MIGRATION_022_PATH = Path("src/db/migrations/versions/022_case_working_context.py")
PHASE44_TABLES = {
    "thread_case_links",
    "case_working_contexts",
    "case_working_context_revisions",
}
CASE_WORKING_CONTEXT_ARRAY_COLUMNS = {
    "claims_json",
    "verified_facts_json",
    "missing_info_json",
    "evidence_refs_json",
    "actions_taken_json",
    "policy_refs_json",
    "agent_recommendations_json",
    "pending_tasks_json",
    "commitments_json",
}
CASE_WORKING_CONTEXT_OBJECT_COLUMNS = {"next_action_json", "source_ref_json"}
REVISION_OBJECT_COLUMNS = {"snapshot_json", "source_ref_json"}


def _alembic_config(database_url: str) -> Config:
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", database_url)
    cfg.attributes["database_url"] = database_url

    import src.config as config_module

    config_module.settings.database_url = database_url
    config_module.get_settings.cache_clear()
    return cfg


def _require_postgres(database_url: str = TEST_DATABASE_URL) -> str:
    try:
        asyncio.run(_ensure_test_database(database_url))
    except (OSError, asyncpg.PostgresError) as exc:
        pytest.skip(f"PostgreSQL unavailable: {exc}")
    return database_url


async def _reset_database(database_url: str) -> None:
    engine = create_async_engine(database_url, future=True, poolclass=NullPool)
    try:
        async with engine.begin() as conn:
            await conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
            await conn.execute(text("CREATE SCHEMA public"))
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
    finally:
        await engine.dispose()


async def _table_names(database_url: str) -> set[str]:
    engine = create_async_engine(database_url, future=True, poolclass=NullPool)
    try:
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'"))
            return {row[0] for row in result}
    finally:
        await engine.dispose()


async def _memory_type_check_definition(database_url: str) -> str:
    engine = create_async_engine(database_url, future=True, poolclass=NullPool)
    try:
        async with engine.connect() as conn:
            result = await conn.execute(
                text(
                    """
                    SELECT pg_get_constraintdef(pg_constraint.oid)
                    FROM pg_constraint
                    JOIN pg_class ON pg_class.oid = pg_constraint.conrelid
                    WHERE pg_class.relname = 'memory_write_events'
                      AND pg_constraint.conname = 'ck_memory_write_events_memory_type'
                    """
                )
            )
            value = result.scalar_one()
            return str(value)
    finally:
        await engine.dispose()


async def _insert_case_working_context_audit_row(database_url: str) -> None:
    tenant_id = uuid.uuid4()
    run_id = uuid.uuid4()
    now = datetime.now(UTC)
    engine = create_async_engine(database_url, future=True, poolclass=NullPool)
    try:
        async with engine.begin() as conn:
            await conn.execute(
                text("INSERT INTO tenants (id, name, status) VALUES (:id, :name, 'active')"),
                {"id": tenant_id, "name": "phase44-schema-tenant"},
            )
            await conn.execute(
                text(
                    """
                    INSERT INTO agent_runs (
                        id, thread_id, tenant_id, user_id, input_query, final_status,
                        scope_classification, started_at
                    )
                    VALUES (
                        :id, 'phase44-thread', :tenant_id, :user_id, 'phase44 schema test',
                        'completed', 'unknown_legacy', :started_at
                    )
                    """
                ),
                {"id": run_id, "tenant_id": tenant_id, "user_id": uuid.uuid4(), "started_at": now},
            )
            await conn.execute(
                text(
                    """
                    INSERT INTO memory_write_events (
                        id, tenant_id, run_id, memory_type, memory_id, decision,
                        reason_code, pii_classification, candidate_hash
                    )
                    VALUES (
                        :id, :tenant_id, :run_id, 'case_working_context', :memory_id,
                        'write', 'phase44_schema_test', 'none', :candidate_hash
                    )
                    """
                ),
                {
                    "id": uuid.uuid4(),
                    "tenant_id": tenant_id,
                    "run_id": run_id,
                    "memory_id": uuid.uuid4(),
                    "candidate_hash": "phase44-candidate-hash",
                },
            )
    finally:
        await engine.dispose()


async def _delete_case_working_context_audit_rows(database_url: str) -> None:
    engine = create_async_engine(database_url, future=True, poolclass=NullPool)
    try:
        async with engine.begin() as conn:
            await conn.execute(
                text("DELETE FROM memory_write_events WHERE memory_type = 'case_working_context'")
            )
    finally:
        await engine.dispose()


def _migration_column_keywords(table_name: str) -> dict[str, set[str]]:
    assert MIGRATION_022_PATH.exists(), "022_case_working_context.py migration must exist"
    tree = ast.parse(MIGRATION_022_PATH.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Attribute) or node.func.attr != "create_table":
            continue
        first_arg = node.args[0] if node.args else None
        if not isinstance(first_arg, ast.Constant) or first_arg.value != table_name:
            continue
        columns: dict[str, set[str]] = {}
        for arg in node.args[1:]:
            if not isinstance(arg, ast.Call):
                continue
            if not isinstance(arg.func, ast.Attribute) or arg.func.attr != "Column":
                continue
            column_name_arg = arg.args[0] if arg.args else None
            if isinstance(column_name_arg, ast.Constant) and isinstance(column_name_arg.value, str):
                columns[column_name_arg.value] = {keyword.arg for keyword in arg.keywords if keyword.arg}
        return columns
    raise AssertionError(f"migration must create {table_name}")


def _migration_nonnullable_columns(table_name: str) -> set[str]:
    assert MIGRATION_022_PATH.exists(), "022_case_working_context.py migration must exist"
    tree = ast.parse(MIGRATION_022_PATH.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Attribute) or node.func.attr != "create_table":
            continue
        first_arg = node.args[0] if node.args else None
        if not isinstance(first_arg, ast.Constant) or first_arg.value != table_name:
            continue
        columns: set[str] = set()
        for arg in node.args[1:]:
            if not isinstance(arg, ast.Call):
                continue
            if not isinstance(arg.func, ast.Attribute) or arg.func.attr != "Column":
                continue
            column_name_arg = arg.args[0] if arg.args else None
            if not isinstance(column_name_arg, ast.Constant) or not isinstance(column_name_arg.value, str):
                continue
            for keyword in arg.keywords:
                if keyword.arg == "nullable" and isinstance(keyword.value, ast.Constant) and keyword.value.value is False:
                    columns.add(column_name_arg.value)
        return columns
    raise AssertionError(f"migration must create {table_name}")


def _check_constraint_text(table_name: str) -> str:
    table = Base.metadata.tables[table_name]
    return "\n".join(
        str(constraint.sqltext) for constraint in table.constraints if isinstance(constraint, CheckConstraint)
    )


def test_phase44_schema_metadata_declares_tables_and_audit_type() -> None:
    assert PHASE44_TABLES.issubset(Base.metadata.tables)

    assert "case_working_context" in _check_constraint_text("memory_write_events")
    assert "authority_class = 'contextual_only'" in _check_constraint_text("case_working_contexts")
    assert "version > 0" in _check_constraint_text("case_working_context_revisions")
    assert (
        MemoryPolicyDecision(
            memory_type="case_working_context",
            decision="write",
            review_status="auto_approved",
            reason_code="phase44_schema_test",
        ).memory_type
        == "case_working_context"
    )


def test_case_working_context_nullable_defaults_match_migration() -> None:
    cwc_table = Base.metadata.tables["case_working_contexts"]
    revision_table = Base.metadata.tables["case_working_context_revisions"]

    cwc_nonnullable = {"schema_version"} | CASE_WORKING_CONTEXT_ARRAY_COLUMNS | CASE_WORKING_CONTEXT_OBJECT_COLUMNS
    revision_nonnullable = REVISION_OBJECT_COLUMNS

    for column_name in cwc_nonnullable:
        assert cwc_table.c[column_name].nullable is False
        assert cwc_table.c[column_name].server_default is not None
    for column_name in revision_nonnullable:
        assert revision_table.c[column_name].nullable is False
        assert revision_table.c[column_name].server_default is not None

    cwc_migration_nonnullable = _migration_nonnullable_columns("case_working_contexts")
    revision_migration_nonnullable = _migration_nonnullable_columns("case_working_context_revisions")
    assert cwc_nonnullable.issubset(cwc_migration_nonnullable)
    assert revision_nonnullable.issubset(revision_migration_nonnullable)

    cwc_migration_keywords = _migration_column_keywords("case_working_contexts")
    revision_migration_keywords = _migration_column_keywords("case_working_context_revisions")
    for column_name in cwc_nonnullable:
        assert "server_default" in cwc_migration_keywords[column_name]
    for column_name in revision_nonnullable:
        assert "server_default" in revision_migration_keywords[column_name]


def test_phase44_migration_upgrade_insert_and_downgrade_guard() -> None:
    database_url = _require_postgres()
    asyncio.run(_reset_database(database_url))
    cfg = _alembic_config(database_url)

    command.upgrade(cfg, "head")
    upgraded_tables = asyncio.run(_table_names(database_url))
    assert PHASE44_TABLES.issubset(upgraded_tables)

    asyncio.run(_insert_case_working_context_audit_row(database_url))
    assert "case_working_context" in asyncio.run(_memory_type_check_definition(database_url))

    with pytest.raises(RuntimeError, match="memory_type='case_working_context'"):
        command.downgrade(cfg, "-1")
    assert "case_working_context" in asyncio.run(_memory_type_check_definition(database_url))

    asyncio.run(_delete_case_working_context_audit_rows(database_url))
    command.downgrade(cfg, "-1")
    downgraded_tables = asyncio.run(_table_names(database_url))
    assert downgraded_tables.isdisjoint({"case_working_contexts", "case_working_context_revisions"})
    assert "case_working_context" not in asyncio.run(_memory_type_check_definition(database_url))

    command.upgrade(cfg, "head")
    reupgraded_tables = asyncio.run(_table_names(database_url))
    assert PHASE44_TABLES.issubset(reupgraded_tables)
