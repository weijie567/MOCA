from __future__ import annotations

import asyncio
import ast
import uuid
from collections.abc import Iterable
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from src.db.models import Base
from tests.conftest import TEST_DATABASE_URL, _ensure_test_database


MIGRATION_PATH = Path("src/db/migrations/versions/011_memory_foundation_v2.py")
THREAD_SCOPE_MIGRATION_PATH = Path("src/db/migrations/versions/012_thread_user_scope.py")
PHASE_TABLES = {
    "conversation_threads",
    "conversation_messages",
    "tool_calls",
    "tool_results",
    "summaries",
}
EXPECTED_COLUMNS = {
    "conversation_threads": {
        "id",
        "tenant_id",
        "thread_id",
        "user_id",
        "case_id",
        "status",
        "archived_at",
        "retention_until",
        "deleted_at",
        "created_at",
        "updated_at",
    },
    "conversation_messages": {
        "id",
        "conversation_thread_id",
        "tenant_id",
        "thread_id",
        "run_id",
        "trace_id",
        "message_index",
        "role",
        "content",
        "content_hash",
        "prompt_template_version",
        "prompt_block_hashes_json",
        "context_snapshot_ref",
        "redacted_prompt_snapshot_ref",
        "metadata_json",
        "archived_at",
        "retention_until",
        "deleted_at",
        "created_at",
        "updated_at",
    },
    "tool_calls": {
        "id",
        "conversation_thread_id",
        "message_id",
        "conversation_message_id",
        "tenant_id",
        "thread_id",
        "run_id",
        "trace_id",
        "tool_call_id",
        "tool_name",
        "caller_node",
        "operation_id",
        "attempt",
        "argument_summary_json",
        "argument_hash",
        "redaction_policy_version",
        "status",
        "started_at",
        "completed_at",
        "latency_ms",
        "error_summary",
        "archived_at",
        "retention_until",
        "deleted_at",
        "created_at",
        "updated_at",
    },
    "tool_results": {
        "id",
        "conversation_thread_id",
        "tool_call_record_id",
        "tenant_id",
        "thread_id",
        "run_id",
        "trace_id",
        "operation_id",
        "conversation_message_id",
        "tool_call_id",
        "tool_result_id",
        "status",
        "source_system",
        "data_freshness_at",
        "latency_ms",
        "raw_result_ref",
        "raw_result_hash",
        "normalized_result_json",
        "summary",
        "prompt_summary",
        "business_fact_refs_json",
        "policy_evidence_refs_json",
        "audit_ref",
        "replay_event_id",
        "archived_at",
        "retention_until",
        "deleted_at",
        "created_at",
        "updated_at",
    },
    "summaries": {
        "id",
        "tenant_id",
        "thread_id",
        "conversation_thread_id",
        "case_id",
        "summary_type",
        "source_start_message_id",
        "source_end_message_id",
        "source_message_ids_json",
        "source_tool_result_ids_json",
        "summary_text",
        "summary_json",
        "summary_model",
        "summary_prompt_version",
        "summary_hash",
        "archived_at",
        "retention_until",
        "deleted_at",
        "created_at",
        "updated_at",
    },
}
FORBIDDEN_STORAGE_COLUMNS = {
    "raw_prompt",
    "raw_args",
    "raw_payload",
    "raw_tool_output",
    "private_reasoning",
    "chain_of_thought",
    "approval_authority_body",
    "action_authority_body",
}


def _table_columns(table_name: str) -> set[str]:
    assert table_name in Base.metadata.tables
    return set(Base.metadata.tables[table_name].c.keys())


def _migration_source() -> str:
    assert MIGRATION_PATH.exists(), "011_memory_foundation_v2.py migration must exist"
    return MIGRATION_PATH.read_text(encoding="utf-8")


def _created_columns_from_migration(source: str, table_name: str) -> set[str]:
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Attribute) or node.func.attr != "create_table":
            continue
        if not node.args or not isinstance(node.args[0], ast.Constant) or node.args[0].value != table_name:
            continue
        columns: set[str] = set()
        for arg in node.args[1:]:
            if isinstance(arg, ast.Call) and isinstance(arg.func, ast.Attribute) and arg.func.attr == "Column":
                first_arg = arg.args[0]
                if isinstance(first_arg, ast.Constant) and isinstance(first_arg.value, str):
                    columns.add(first_arg.value)
            if isinstance(arg, ast.Starred) and isinstance(arg.value, ast.Call):
                helper = arg.value.func
                if isinstance(helper, ast.Name) and helper.id == "_retention_columns":
                    columns.update({"archived_at", "retention_until", "deleted_at"})
                if isinstance(helper, ast.Name) and helper.id == "_timestamps":
                    columns.update({"created_at", "updated_at"})
        return columns
    raise AssertionError(f"migration must create {table_name}")


async def _reset_database(database_url: str) -> None:
    await _ensure_test_database(database_url)
    engine = create_async_engine(database_url, future=True, poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.execute(text("DROP SCHEMA public CASCADE"))
        await conn.execute(text("CREATE SCHEMA public"))
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
    await engine.dispose()


async def _table_names(database_url: str) -> set[str]:
    engine = create_async_engine(database_url, future=True, poolclass=NullPool)
    async with engine.connect() as conn:
        names = await conn.run_sync(lambda sync_conn: set(inspect(sync_conn).get_table_names()))
    await engine.dispose()
    return names


async def _insert_active_thread_id_duplicates(database_url: str) -> None:
    tenant_id = uuid.uuid4()
    user_ids = [uuid.uuid4(), uuid.uuid4()]
    engine = create_async_engine(database_url, future=True, poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.execute(
            text("INSERT INTO tenants (id, name, status) VALUES (:id, :name, 'active')"),
            {"id": tenant_id, "name": "thread-scope-downgrade-tenant"},
        )
        for index, user_id in enumerate(user_ids):
            await conn.execute(
                text(
                    """
                    INSERT INTO users (id, tenant_id, username, password_hash, role, is_active)
                    VALUES (:id, :tenant_id, :username, 'hash', 'admin', true)
                    """
                ),
                {"id": user_id, "tenant_id": tenant_id, "username": f"thread_scope_user_{index}"},
            )
            await conn.execute(
                text(
                    """
                    INSERT INTO conversation_threads (id, tenant_id, user_id, thread_id, status)
                    VALUES (:id, :tenant_id, :user_id, 'shared-thread-id', 'active')
                    """
                ),
                {"id": uuid.uuid4(), "tenant_id": tenant_id, "user_id": user_id},
            )
    await engine.dispose()


def _alembic_config(database_url: str) -> Config:
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", database_url)
    cfg.attributes["database_url"] = database_url

    import src.config as config_module

    config_module.settings.database_url = database_url
    config_module.get_settings.cache_clear()
    return cfg


def test_memory_foundation_orm_declares_expected_tables_and_columns() -> None:
    assert PHASE_TABLES.issubset(Base.metadata.tables)
    for table_name, expected_columns in EXPECTED_COLUMNS.items():
        assert expected_columns.issubset(_table_columns(table_name))


def test_memory_foundation_orm_excludes_raw_prompt_and_authority_payload_columns() -> None:
    for table_name in PHASE_TABLES:
        assert _table_columns(table_name).isdisjoint(FORBIDDEN_STORAGE_COLUMNS)


def test_memory_foundation_orm_and_migration_columns_match() -> None:
    source = _migration_source()
    assert 'revision: str = "011_memory_foundation_v2"' in source
    assert 'down_revision: str | None = "010_replay_event_v3"' in source

    for table_name, expected_columns in EXPECTED_COLUMNS.items():
        orm_columns = _table_columns(table_name)
        migration_columns = _created_columns_from_migration(source, table_name)
        assert expected_columns.issubset(orm_columns)
        assert orm_columns == migration_columns


def test_memory_foundation_migration_declares_downgrade_to_010_replay_event_v3() -> None:
    source = _migration_source()
    assert "def downgrade" in source
    for table_name in ("summaries", "tool_results", "tool_calls", "conversation_messages", "conversation_threads"):
        assert f'op.drop_table("{table_name}")' in source


def test_memory_foundation_migration_downgrade_round_trip() -> None:
    database_url = TEST_DATABASE_URL
    asyncio.run(_reset_database(database_url))
    cfg = _alembic_config(database_url)

    command.upgrade(cfg, "head")
    upgraded_tables = asyncio.run(_table_names(database_url))
    assert PHASE_TABLES.issubset(upgraded_tables)
    assert "agent_trace_events" in upgraded_tables

    command.downgrade(cfg, "010_replay_event_v3")
    downgraded_tables = asyncio.run(_table_names(database_url))
    assert downgraded_tables.isdisjoint(PHASE_TABLES)
    assert "agent_trace_events" in downgraded_tables

    command.upgrade(cfg, "head")
    reupgraded_tables = asyncio.run(_table_names(database_url))
    assert PHASE_TABLES.issubset(reupgraded_tables)


def test_thread_user_scope_migration_downgrade_fails_on_active_duplicate_threads() -> None:
    database_url = TEST_DATABASE_URL
    asyncio.run(_reset_database(database_url))
    cfg = _alembic_config(database_url)

    command.upgrade(cfg, "head")
    asyncio.run(_insert_active_thread_id_duplicates(database_url))

    with pytest.raises(RuntimeError, match="Cannot downgrade 012_thread_user_scope"):
        command.downgrade(cfg, "011_memory_foundation_v2")

    source = THREAD_SCOPE_MIGRATION_PATH.read_text(encoding="utf-8")
    assert "HAVING COUNT(*) > 1" in source
    assert "Archive, delete, or merge" in source


@pytest.mark.parametrize("table_name", sorted(PHASE_TABLES))
def test_memory_foundation_migration_does_not_create_phase_16_memory_surfaces(table_name: str) -> None:
    source = _migration_source()
    assert table_name in source
    forbidden_patterns: Iterable[str] = ("case_memories", "memory_tombstones", "embedding", "vector")
    for pattern in forbidden_patterns:
        assert pattern not in source
