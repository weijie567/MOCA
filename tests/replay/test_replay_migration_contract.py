from __future__ import annotations

from pathlib import Path
import re

from sqlalchemy import CheckConstraint, Index, UniqueConstraint
from sqlalchemy.schema import ColumnCollectionConstraint

from src.db.models import Base
from src.replay.validators import REPLAY_EVENT_TYPES


V3_MIGRATION_PATH = Path("src/db/migrations/versions/010_replay_event_v3.py")
TOOL_POLICY_MIGRATION_PATH = Path("src/db/migrations/versions/017_tool_policy_events.py")
V3_COLUMNS = {
    "parent_operation_id",
    "attempt",
    "version",
    "node_name",
    "approval_id",
    "draft_id",
    "tool_call_id",
    "evidence_refs_json",
    "error_json",
    "archived_at",
    "retention_until",
    "deleted_at",
}
REQUIRED_INDEXES = {
    "ix_agent_trace_events_tenant_run_sequence": {"tenant_id", "run_id", "sequence"},
    "ix_agent_trace_events_tenant_run_operation": {"tenant_id", "run_id", "operation_id"},
    "ix_agent_trace_events_tenant_occurred_at": {"tenant_id", "occurred_at"},
    "ix_agent_trace_events_event_type_occurred_at": {"event_type", "occurred_at"},
}


def _table(name: str):
    assert name in Base.metadata.tables
    return Base.metadata.tables[name]


def _column_names(table_name: str) -> set[str]:
    return set(_table(table_name).c.keys())


def _named_schema_items(table_name: str) -> dict[str, UniqueConstraint | CheckConstraint | Index]:
    table = _table(table_name)
    named_items: dict[str, UniqueConstraint | CheckConstraint | Index] = {}
    for item in [*table.constraints, *table.indexes]:
        if item.name:
            named_items[item.name] = item
    return named_items


def _item_columns(item: UniqueConstraint | CheckConstraint | Index) -> set[str]:
    if isinstance(item, ColumnCollectionConstraint | Index):
        return {column.name for column in item.columns}
    return set()


def _read_migration(path: Path, label: str) -> str:
    assert path.exists(), f"{label} migration must exist at {path}"
    return path.read_text(encoding="utf-8")


def _event_type_check_values(source: str) -> set[str]:
    match = re.search(r"ck_agent_trace_events_event_type.*?event_type\s+IN\s+\((?P<values>.*?)\)", source, re.S)
    assert match, "ck_agent_trace_events_event_type must declare event_type IN (...)"
    return set(re.findall(r"'([^']+)'", match.group("values")))


def test_agent_trace_event_declares_v3_expand_columns_and_indexes():
    assert V3_COLUMNS.issubset(_column_names("agent_trace_events"))

    items = _named_schema_items("agent_trace_events")
    assert _item_columns(items["uq_agent_trace_events_run_seq"]) == {"run_id", "sequence"}
    for index_name, columns in REQUIRED_INDEXES.items():
        assert _item_columns(items[index_name]) == columns


def test_migration_010_revision_adds_v3_columns_checks_and_indexes():
    source = _read_migration(V3_MIGRATION_PATH, "010_replay_event_v3")

    assert 'revision: str = "010_replay_event_v3"' in source
    assert 'down_revision: str | None = "009_action_draft_v2"' in source
    assert "minimal_event_envelope.v1" in source
    assert "replay_event.v3" in source
    assert "ck_agent_trace_events_event_type" in source
    assert "event_type IN" in source
    assert "sequence > 0" in source
    assert "attempt IS NULL OR attempt > 0" in source

    for column_name in V3_COLUMNS:
        assert f'"{column_name}"' in source
    for index_name in REQUIRED_INDEXES:
        assert index_name in source


def test_migration_010_event_type_check_matches_original_registry():
    """Migration 010's check constraint must match its own era's event types."""
    source = _read_migration(V3_MIGRATION_PATH, "010_replay_event_v3")
    v3_check_values = _event_type_check_values(source)
    # The 010 migration should have exactly the pre-Phase-29 event types.
    assert v3_check_values == REPLAY_EVENT_TYPES - {
        "tool_policy_visibility_recorded",
        "tool_policy_runtime_auth_recorded",
    }


def test_migration_preserves_minimal_rows_without_v3_backwrite():
    source = _read_migration(V3_MIGRATION_PATH, "010_replay_event_v3")
    normalized_source = re.sub(r"\s+", " ", source.lower())

    assert "minimal_event_envelope.v1" in normalized_source
    assert "replay_event.v3" in normalized_source
    assert not re.search(r"update agent_trace_events.*replay_event\.v3", normalized_source)
    assert not re.search(r"schema_version.*replay_event\.v3.*where", normalized_source)


def test_tool_policy_migration_event_type_check_matches_replay_event_registry():
    # Phase 29 D-06/D-10: the latest event-type check migration (017_tool_policy_events)
    # must register tool_policy_visibility_recorded / tool_policy_runtime_auth_recorded
    # and its check values must equal src.replay.validators.REPLAY_EVENT_TYPES.
    source = _read_migration(TOOL_POLICY_MIGRATION_PATH, "017_tool_policy_events")

    assert 'revision: str = "017_tool_policy_events"' in source
    assert 'down_revision: str | None = "016_agent_run_memory_idempotency"' in source
    assert "tool_policy_visibility_recorded" in source
    assert "tool_policy_runtime_auth_recorded" in source
    assert re.search(r'op\.drop_constraint\(\s*"ck_agent_trace_events_event_type"', source)
    assert re.search(r'op\.create_check_constraint\(\s*"ck_agent_trace_events_event_type"', source)
    assert _event_type_check_values(source) == REPLAY_EVENT_TYPES


def test_tool_policy_migration_does_not_create_table_or_envelope():
    # D-10: no parallel event table / envelope / schema_version for tool policy.
    source = _read_migration(TOOL_POLICY_MIGRATION_PATH, "017_tool_policy_events")
    assert "create_table" not in source
    assert "CREATE TABLE" not in source
    assert "DecisionEventEnvelopeV2" not in source
    assert "tool_policy_decision.v1" not in source
