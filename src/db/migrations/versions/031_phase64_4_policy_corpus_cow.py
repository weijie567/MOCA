"""Permit copy-on-write corpus projections and complete activation history.

Revision ID: 031_phase64_4_policy_corpus_cow
Revises: 030_phase64_4_token_corpora
Create Date: 2026-08-11

Current block rows are corpus-local projections.  A stable source block id may
therefore occur in several retained corpora for one logical document.  The
non-unique lookup index remains in place, while active corpus bindings provide
the visibility scope.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "031_phase64_4_policy_corpus_cow"
down_revision: str | None = "030_phase64_4_token_corpora"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(
        "uq_document_blocks_tenant_doc_source_block",
        "document_blocks",
        type_="unique",
    )
    op.add_column(
        "policy_corpus_activation_history",
        sa.Column(
            "prior_rollout_epoch",
            sa.BigInteger(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.add_column(
        "policy_corpus_activation_history",
        sa.Column(
            "actor",
            sa.String(length=128),
            nullable=False,
            server_default=sa.text("'moca.phase64_4.bootstrap'"),
        ),
    )
    op.create_check_constraint(
        "ck_policy_corpus_activation_history_prior_epoch_nonnegative",
        "policy_corpus_activation_history",
        "prior_rollout_epoch >= 0",
    )
    op.alter_column(
        "policy_corpus_activation_history",
        "prior_rollout_epoch",
        server_default=None,
    )
    op.alter_column(
        "policy_corpus_activation_history",
        "actor",
        server_default=None,
    )


def downgrade() -> None:
    duplicate_exists = bool(
        op.get_bind()
        .execute(
            sa.text(
                "SELECT EXISTS ("
                "SELECT 1 FROM document_blocks "
                "GROUP BY tenant_id, doc_id, source_block_id HAVING count(*) > 1"
                ")"
            )
        )
        .scalar_one()
    )
    if duplicate_exists:
        raise RuntimeError("refusing downgrade: duplicate document block identities exist")

    op.drop_constraint(
        "ck_policy_corpus_activation_history_prior_epoch_nonnegative",
        "policy_corpus_activation_history",
        type_="check",
    )
    op.drop_column("policy_corpus_activation_history", "actor")
    op.drop_column("policy_corpus_activation_history", "prior_rollout_epoch")
    op.create_unique_constraint(
        "uq_document_blocks_tenant_doc_source_block",
        "document_blocks",
        ["tenant_id", "doc_id", "source_block_id"],
    )
