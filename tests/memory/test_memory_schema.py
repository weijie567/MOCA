from __future__ import annotations

from pathlib import Path

from sqlalchemy import CheckConstraint

from src.db.models import Base


MIGRATION_PATH = Path("src/db/migrations/versions/013_long_term_case_memory.py")
PHASE16_TABLES = {
    "long_term_memories",
    "case_memories",
    "memory_tombstones",
    "memory_write_events",
}
REVIEW_STATUSES = {
    "auto_approved",
    "needs_review",
    "approved",
    "rejected",
    "superseded",
    "tombstoned",
    "deleted",
}
PII_CLASSIFICATIONS = {"none", "low", "sensitive", "prohibited"}
REQUIRED_MIGRATION_INDEXES = {
    "uq_long_term_memories_active_identity",
    "ix_long_term_memories_active_retrieval",
    "ix_long_term_memories_source_identity",
    "ix_case_memories_metadata_filters",
    "ix_case_memories_active_content_identity",
    "ix_case_memories_source_identity",
    "ix_case_memories_embedding_hnsw",
    "ix_memory_tombstones_active_content_identity",
    "ix_memory_tombstones_active_source_identity",
    "ix_memory_tombstones_active_scope",
    "ix_memory_write_events_tenant_run",
}


def _migration_source() -> str:
    assert MIGRATION_PATH.exists(), "Phase 16 memory schema migration must exist"
    return MIGRATION_PATH.read_text(encoding="utf-8")


def _table_columns(table_name: str) -> set[str]:
    assert table_name in Base.metadata.tables
    return set(Base.metadata.tables[table_name].c.keys())


def _check_constraint_text() -> str:
    parts: list[str] = []
    for table_name in PHASE16_TABLES:
        table = Base.metadata.tables.get(table_name)
        assert table is not None
        parts.extend(
            str(constraint.sqltext)
            for constraint in table.constraints
            if isinstance(constraint, CheckConstraint)
        )
    return "\n".join(parts)


def test_phase16_memory_tables_exist() -> None:
    assert PHASE16_TABLES.issubset(Base.metadata.tables)

    source = _migration_source()
    for table_name in PHASE16_TABLES:
        assert f'op.create_table("{table_name}"' in source


def test_case_memory_has_content_and_source_identity_columns() -> None:
    expected_columns = {"content_hash", "source_identity_hash"}

    assert expected_columns.issubset(_table_columns("case_memories"))

    source = _migration_source()
    case_table_start = source.index('op.create_table("case_memories"')
    case_table_end = source.index('op.create_table("memory_tombstones"', case_table_start)
    case_table_source = source[case_table_start:case_table_end]
    for column_name in expected_columns:
        assert f'"{column_name}"' in case_table_source


def test_memory_lifecycle_check_constraints_exist() -> None:
    constraint_text = _check_constraint_text()
    for status in REVIEW_STATUSES:
        assert status in constraint_text
    for classification in PII_CLASSIFICATIONS:
        assert classification in constraint_text

    source = _migration_source()
    for status in REVIEW_STATUSES:
        assert status in source
    for classification in PII_CLASSIFICATIONS:
        assert classification in source


def test_memory_tombstone_active_identity_index_exists() -> None:
    tombstone_table = Base.metadata.tables["memory_tombstones"]
    expected_columns = {"tenant_id", "memory_type", "scope_type", "scope_id", "content_hash"}
    assert any(
        expected_columns.issubset({column.name for column in index.columns})
        for index in tombstone_table.indexes
    )

    source = _migration_source()
    active_index_start = source.index("ix_memory_tombstones_active_content_identity")
    active_index_source = source[active_index_start : source.index(")", active_index_start)]
    for column_name in expected_columns:
        assert f'"{column_name}"' in active_index_source


def test_case_memory_embedding_index_matches_hnsw_migration() -> None:
    case_table = Base.metadata.tables["case_memories"]
    index_names = {index.name for index in case_table.indexes}

    assert "ix_case_memories_embedding_hnsw" in index_names
    assert "ix_case_memories_embedding_vector" not in index_names


def test_phase16_memory_migration_preflight_objects_are_declared() -> None:
    source = _migration_source()

    assert "def upgrade() -> None:" in source
    assert "def downgrade() -> None:" in source
    assert "session_memories" not in source
    for table_name in PHASE16_TABLES:
        assert f'op.create_table("{table_name}"' in source
    for index_name in REQUIRED_MIGRATION_INDEXES:
        assert index_name in source
    for constraint_name in (
        "ck_long_term_memories_review_status",
        "ck_case_memories_review_status",
        "ck_memory_tombstones_memory_type",
        "ck_memory_write_events_decision",
    ):
        assert constraint_name in source


def test_phase16_memory_migration_downgrade_drops_tables_in_reverse_dependency_order() -> None:
    source = _migration_source()
    expected_drop_order = [
        "memory_write_events",
        "memory_tombstones",
        "case_memories",
        "long_term_memories",
    ]

    positions = [source.index(f'op.drop_table("{table_name}")') for table_name in expected_drop_order]
    assert positions == sorted(positions)
