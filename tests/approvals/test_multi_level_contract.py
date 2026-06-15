from __future__ import annotations

from pathlib import Path

from sqlalchemy import Index

from src.db.models import Base


MIGRATION_PATH = Path("src/db/migrations/versions/008_approval_state_machine.py")


def _table(name: str):
    assert name in Base.metadata.tables
    return Base.metadata.tables[name]


def _columns(table_name: str) -> set[str]:
    return set(_table(table_name).c.keys())


def _index(name: str, table_name: str) -> Index:
    for index in _table(table_name).indexes:
        if index.name == name:
            return index
    raise AssertionError(f"missing index {name}")


def _index_columns(name: str, table_name: str) -> set[str]:
    return {column.name for column in _index(name, table_name).columns}


def _migration_source() -> str:
    assert MIGRATION_PATH.exists(), "migration 008 must exist"
    return MIGRATION_PATH.read_text(encoding="utf-8")


def test_level_metadata_supports_any_one_and_all_modes():
    level_columns = _columns("approval_levels")

    assert "mode" in level_columns
    assert "any_one" in {"any_one", "all"}
    assert "all" in {"any_one", "all"}

    source = _migration_source()
    assert "any_one" in source
    assert "all" in source


def test_request_level_assignment_version_fields_exist_for_cas():
    assert {"revision", "version"}.issubset(_columns("approval_requests"))
    assert {"version", "level_number"}.issubset(_columns("approval_levels"))
    assert {"version"}.issubset(_columns("approval_assignments"))


def test_decisions_and_events_carry_redundant_request_bindings():
    redundant_fields = {
        "tenant_id",
        "run_id",
        "thread_id",
        "request_revision",
        "request_version",
        "level_version",
        "level_mode",
        "assignment_version",
    }

    assert redundant_fields.issubset(_columns("approval_decisions"))
    assert (redundant_fields - {"level_mode"}).issubset(_columns("approval_events"))


def test_any_one_winning_accept_and_active_assignment_uniques_are_partial_indexes():
    active_assignment = _index("uq_approval_decisions_active_assignment", "approval_decisions")
    winning_accept = _index("uq_approval_decisions_winning_accept_level", "approval_decisions")

    assert active_assignment.unique
    assert winning_accept.unique
    assert _index_columns("uq_approval_decisions_active_assignment", "approval_decisions") == {
        "approval_assignment_id",
    }
    assert _index_columns("uq_approval_decisions_winning_accept_level", "approval_decisions") == {
        "approval_level_id",
    }

    active_where = str(active_assignment.dialect_options["postgresql"]["where"])
    winning_where = str(winning_accept.dialect_options["postgresql"]["where"])
    assert "deleted_at IS NULL" in active_where
    assert "archived_at IS NULL" in active_where
    assert "decision_type" in active_where
    assert "level_mode = 'any_one'" in winning_where
    assert "accept" in winning_where
    assert "deleted_at IS NULL" in winning_where
