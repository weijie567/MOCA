from __future__ import annotations

from pathlib import Path


TOKEN_CORPUS_MIGRATION = Path("src/db/migrations/versions/030_phase64_4_token_corpora.py")


def test_rag_migration_backfills_unique_doc_keys_before_constraint():
    migration = Path("src/db/migrations/versions/002_rag_pipeline.py").read_text()

    assert 'server_default=""' not in migration
    assert "nullable=True" in migration
    assert "UPDATE policy_documents" in migration
    assert "'legacy_' || replace(id::text, '-', '')" in migration
    assert migration.index("UPDATE policy_documents") < migration.index("create_unique_constraint")


def test_token_corpus_migration_keeps_visibility_out_of_immutable_identity() -> None:
    migration = TOKEN_CORPUS_MIGRATION.read_text(encoding="utf-8")

    assert "corpus_document_bindings" in migration
    assert "corpus_block_bindings" in migration
    assert "corpus_chunk_bindings" in migration
    assert "policy_document_versions" in migration
    assert "policy_chunk_versions" in migration
    immutable_column_additions = [
        line
        for line in migration.splitlines()
        if "op.add_column" in line and ("policy_document_versions" in line or "policy_chunk_versions" in line)
    ]
    assert all("corpus" not in line for line in immutable_column_additions)
    assert "corpus_version_id" not in "\n".join(immutable_column_additions)
