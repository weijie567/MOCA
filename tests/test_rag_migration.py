from __future__ import annotations

from pathlib import Path


def test_rag_migration_backfills_unique_doc_keys_before_constraint():
    migration = Path("src/db/migrations/versions/002_rag_pipeline.py").read_text()

    assert "server_default=\"\"" not in migration
    assert "nullable=True" in migration
    assert "UPDATE policy_documents" in migration
    assert "'legacy_' || replace(id::text, '-', '')" in migration
    assert migration.index("UPDATE policy_documents") < migration.index("create_unique_constraint")
