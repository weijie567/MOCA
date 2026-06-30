from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest


MIGRATION_PATH = Path("src/db/migrations/versions/019_phase36_merchant_scope_hardening.py")


def _migration_source() -> str:
    assert MIGRATION_PATH.exists(), "migration 019_phase36_merchant_scope_hardening must exist"
    return MIGRATION_PATH.read_text(encoding="utf-8")


def _load_migration() -> ModuleType:
    assert MIGRATION_PATH.exists(), "migration 019_phase36_merchant_scope_hardening must exist"
    spec = importlib.util.spec_from_file_location("phase36_migration", MIGRATION_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _FakeResult:
    def __init__(self, row: dict[str, Any] | None) -> None:
        self._row = row

    def mappings(self) -> _FakeResult:
        return self

    def first(self) -> dict[str, Any] | None:
        return self._row


class _FakeBind:
    def __init__(self, row: dict[str, Any] | None = None) -> None:
        self.row = row
        self.statements: list[str] = []

    def execute(self, statement: object, *_args: object, **_kwargs: object) -> _FakeResult:
        self.statements.append(str(statement))
        return _FakeResult(self.row)


def _target_ref(target_merchant_id: str = "merchant-1") -> dict[str, Any]:
    return {
        "schema_version": "target_merchant_binding.v1",
        "target_merchant_id": target_merchant_id,
        "source": "business_fact_ref",
        "business_fact_ref": {
            "schema_version": "business_fact_ref.v1",
            "tenant_id": "tenant-1",
            "source_system": "demo_orders_db",
            "resource_type": "order",
            "resource_id": "order-1",
            "fact_version": "2026-06-30T00:00:00.000Z",
            "observed_at": "2026-06-30T00:00:00.000Z",
        },
    }


def test_clean_data_passes_all_phase36_preflight_helpers(monkeypatch: pytest.MonkeyPatch) -> None:
    migration = _load_migration()
    clean_bind = _FakeBind()
    monkeypatch.setattr(migration.op, "get_bind", lambda: clean_bind)

    migration._ensure_active_business_users_have_merchant_binding()
    migration._ensure_no_same_tenant_username_duplicates()
    migration._ensure_agent_run_scope_rows_safe()
    migration._ensure_authorization_root_scope_consistency()
    migration._ensure_no_forbidden_scope_backfill_sources()

    joined_sql = "\n".join(clean_bind.statements).lower()
    assert "users" in joined_sql
    assert "agent_runs" in joined_sql
    assert "approval_requests" in joined_sql
    assert "action_drafts" in joined_sql
    assert "action_safety_snapshots" in joined_sql


@pytest.mark.parametrize("role", ["support", "manager", "merchant"])
def test_active_business_user_with_null_merchant_binding_fails(
    role: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    migration = _load_migration()
    monkeypatch.setattr(
        migration.op,
        "get_bind",
        lambda: _FakeBind(
            {
                "id": "user-1",
                "tenant_id": "tenant-1",
                "role": role,
                "merchant_id": None,
                "merchant_tenant_id": None,
            }
        ),
    )

    with pytest.raises(RuntimeError, match="active business users without tenant-consistent merchant binding"):
        migration._ensure_active_business_users_have_merchant_binding()


def test_active_business_user_with_cross_tenant_merchant_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    migration = _load_migration()
    monkeypatch.setattr(
        migration.op,
        "get_bind",
        lambda: _FakeBind(
            {
                "id": "user-1",
                "tenant_id": "tenant-1",
                "role": "support",
                "merchant_id": "merchant-1",
                "merchant_tenant_id": "tenant-2",
            }
        ),
    )

    with pytest.raises(RuntimeError, match="cross-tenant merchant binding"):
        migration._ensure_active_business_users_have_merchant_binding()


def test_same_tenant_duplicate_username_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    migration = _load_migration()
    monkeypatch.setattr(
        migration.op,
        "get_bind",
        lambda: _FakeBind({"tenant_id": "tenant-1", "username": "demo", "duplicate_count": 2}),
    )

    with pytest.raises(RuntimeError, match="same-tenant duplicate usernames"):
        migration._ensure_no_same_tenant_username_duplicates()


@pytest.mark.parametrize(
    ("row", "message"),
    [
        (
            {
                "id": "run-1",
                "tenant_id": "tenant-1",
                "scope_classification": "business_merchant",
                "target_merchant_id": None,
                "target_merchant_ref": _target_ref(),
                "reason": "missing target_merchant_id",
            },
            "missing target_merchant_id",
        ),
        (
            {
                "id": "run-2",
                "tenant_id": "tenant-1",
                "scope_classification": "business_merchant",
                "target_merchant_id": "merchant-1",
                "target_merchant_ref": None,
                "reason": "missing target_merchant_ref",
            },
            "missing target_merchant_ref",
        ),
        (
            {
                "id": "run-3",
                "tenant_id": "tenant-1",
                "scope_classification": "business_merchant",
                "target_merchant_id": "merchant-1",
                "target_merchant_ref": {"schema_version": "wrong"},
                "reason": "malformed target_merchant_ref",
            },
            "malformed target_merchant_ref",
        ),
        (
            {
                "id": "run-4",
                "tenant_id": "tenant-1",
                "scope_classification": "policy_only",
                "target_merchant_id": "merchant-1",
                "target_merchant_ref": _target_ref(),
                "reason": "non-business scope carries target merchant",
            },
            "non-business scope carries target merchant",
        ),
        (
            {
                "id": "run-5",
                "tenant_id": "tenant-1",
                "scope_classification": "unknown_legacy",
                "target_merchant_id": "merchant-1",
                "target_merchant_ref": _target_ref(),
                "reason": "ambiguous_legacy carries target merchant",
            },
            "ambiguous_legacy",
        ),
    ],
)
def test_agent_run_scope_preflight_rejects_missing_malformed_or_inconsistent_rows(
    row: dict[str, Any],
    message: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    migration = _load_migration()
    monkeypatch.setattr(migration.op, "get_bind", lambda: _FakeBind(row))

    with pytest.raises(RuntimeError, match=message):
        migration._ensure_agent_run_scope_rows_safe()


@pytest.mark.parametrize("root_table", ["approval_requests", "action_drafts", "action_safety_snapshots"])
def test_authorization_root_contradiction_with_business_run_fails(
    root_table: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    migration = _load_migration()
    monkeypatch.setattr(
        migration.op,
        "get_bind",
        lambda: _FakeBind(
            {
                "root_table": root_table,
                "id": "root-1",
                "run_id": "run-1",
                "tenant_id": "tenant-1",
                "root_target_merchant_id": "merchant-2",
                "run_target_merchant_id": "merchant-1",
                "reason": "contradictory target merchant",
            }
        ),
    )

    with pytest.raises(RuntimeError, match=f"{root_table}.*contradictory target merchant"):
        migration._ensure_authorization_root_scope_consistency()


def test_ambiguous_legacy_runs_are_fail_closed_and_forbidden_sources_are_guarded() -> None:
    source = _migration_source()

    assert "ambiguous_legacy" in source
    assert "unknown_legacy" in source
    assert "no_authoritative_scope_proof" in source
    assert "target_merchant_context" not in source
    assert "replay_authorization_proof" not in source
    for forbidden in (
        "requested_by",
        "user.merchant_id",
        "thread_id",
        "input_query",
        "final_response",
        "prompt",
        "memory",
        "rag",
        "llm",
        "raw_tool_payload",
        "raw_payload",
    ):
        assert forbidden in source


def test_downgrade_reupgrade_keeps_legacy_business_rows_present() -> None:
    source = _migration_source()

    assert "downgrade/reupgrade" in source
    assert 'op.drop_column("agent_runs", "target_merchant_id")' in source
    assert 'op.drop_column("approval_requests"' not in source
    assert 'op.drop_column("action_drafts"' not in source
    assert 'op.drop_column("action_safety_snapshots", "target_merchant_id")' in source
    assert "DELETE FROM agent_runs" not in source
    assert "DELETE FROM approval_requests" not in source
    assert "DELETE FROM action_drafts" not in source
    assert "DELETE FROM action_safety_snapshots" not in source
