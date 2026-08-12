from __future__ import annotations

import asyncio
from pathlib import Path
from uuid import uuid4

from alembic import command
from alembic.config import Config
import pytest
from sqlalchemy import CheckConstraint, text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from src.db.models import DocumentBlock, PolicyCorpusActivationHistory
from tests.migration_helpers import upgrade_to_head_with_evidence_cutover


MIGRATION_PATH = Path("src/db/migrations/versions/031_phase64_4_policy_corpus_cow.py")
DATABASE_URL = "postgresql+asyncpg://moca:moca_dev@localhost:5432/moca_test"
MIGRATION_REVISION = "031_phase64_4_policy_corpus_cow"


def _config() -> Config:
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", DATABASE_URL)
    config.attributes["database_url"] = DATABASE_URL
    return config


async def _reset_schema() -> None:
    engine = create_async_engine(DATABASE_URL, future=True, poolclass=NullPool)
    try:
        async with engine.begin() as connection:
            await connection.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
            await connection.execute(text("CREATE SCHEMA public"))
            await connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            await connection.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
    finally:
        await engine.dispose()


def test_cow_orm_removes_cross_corpus_block_identity_and_completes_history_contract() -> None:
    assert MIGRATION_PATH.exists()
    constraint_names = {constraint.name for constraint in DocumentBlock.__table__.constraints}
    assert "uq_document_blocks_tenant_doc_source_block" not in constraint_names
    assert "ix_document_blocks_tenant_doc_source_block" in {index.name for index in DocumentBlock.__table__.indexes}
    assert {
        "prior_rollout_epoch",
        "actor",
    }.issubset(PolicyCorpusActivationHistory.__table__.c.keys())
    assert PolicyCorpusActivationHistory.__table__.c.prior_rollout_epoch.nullable is False
    assert PolicyCorpusActivationHistory.__table__.c.actor.nullable is False
    assert "ck_policy_corpus_activation_history_prior_epoch_nonnegative" in {
        constraint.name
        for constraint in PolicyCorpusActivationHistory.__table__.constraints
        if isinstance(constraint, CheckConstraint)
    }


@pytest.mark.asyncio
async def test_migration031_real_upgrade_and_duplicate_block_downgrade_refusal() -> None:
    await _reset_schema()
    config = _config()
    await upgrade_to_head_with_evidence_cutover(
        config,
        database_url=DATABASE_URL,
        target_revision=MIGRATION_REVISION,
    )

    engine = create_async_engine(DATABASE_URL, future=True, poolclass=NullPool)
    tenant_id = uuid4()
    document_id = uuid4()
    try:
        async with engine.begin() as connection:
            revision = await connection.scalar(text("SELECT version_num FROM alembic_version"))
            assert revision == MIGRATION_REVISION
            unique_constraint = await connection.scalar(
                text("SELECT count(*) FROM pg_constraint WHERE conname = 'uq_document_blocks_tenant_doc_source_block'")
            )
            assert unique_constraint == 0
            columns = {
                row.column_name: (row.is_nullable, row.column_default)
                for row in (
                    await connection.execute(
                        text(
                            "SELECT column_name, is_nullable, column_default "
                            "FROM information_schema.columns "
                            "WHERE table_name = 'policy_corpus_activation_history' "
                            "AND column_name IN ('prior_rollout_epoch', 'actor')"
                        )
                    )
                )
            }
            assert columns == {
                "actor": ("NO", None),
                "prior_rollout_epoch": ("NO", None),
            }
            await connection.execute(
                text("INSERT INTO tenants (id, name, status) VALUES (:id, 'cow-downgrade', 'active')"),
                {"id": tenant_id},
            )
            await connection.execute(
                text(
                    "INSERT INTO policy_documents "
                    "(id, tenant_id, doc_key, doc_type, title, effective_date, risk_level, version, content) "
                    "VALUES (:id, :tenant_id, 'policy-a', 'policy', 'Policy A', CURRENT_DATE, "
                    "'medium', 1, 'content')"
                ),
                {"id": document_id, "tenant_id": tenant_id},
            )
            for block_index in (0, 1):
                await connection.execute(
                    text(
                        "INSERT INTO document_blocks "
                        "(id, tenant_id, doc_id, source_block_id, block_index, block_type, text, "
                        "normalized_text, text_hash, bbox_json, table_metadata_json, "
                        "parser_metadata_json, ocr_metadata_json) "
                        "VALUES (:id, :tenant_id, :doc_id, 'stable-source-id', :block_index, "
                        "'paragraph', :body, :body, :hash, '{}'::jsonb, '{}'::jsonb, "
                        "'{}'::jsonb, '{}'::jsonb)"
                    ),
                    {
                        "id": uuid4(),
                        "tenant_id": tenant_id,
                        "doc_id": document_id,
                        "block_index": block_index,
                        "body": f"version {block_index}",
                        "hash": f"sha256:{block_index:064x}",
                    },
                )
    finally:
        await engine.dispose()

    with pytest.raises(RuntimeError, match="duplicate document block identities exist"):
        await asyncio.to_thread(command.downgrade, config, "030_phase64_4_token_corpora")
