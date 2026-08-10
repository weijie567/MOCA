"""Add evaluation-only durable RAG format-parity round ownership.

Revision ID: 029_phase64_3_rag_eval_rounds
Revises: 028_phase64_2_memory_lifecycle
Create Date: 2026-08-10

Safe downgrade protocol: expire the lease, prove the exact same-owner current
projection, clean only its current children/jobs, transition the owner row to
terminal ``abandoned``, and only then invoke downgrade.  Production policy
heads, immutable evidence history, foreign keys, and triggers are untouched.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "029_phase64_3_rag_eval_rounds"
down_revision: str | None = "028_phase64_2_memory_lifecycle"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


_DOC_KEYS_JSON = (
    '["eval_refund_eligibility_and_return",'
    '"eval_quality_compensation_and_approval",'
    '"eval_cross_border_and_digital_goods"]'
)


def upgrade() -> None:
    op.create_table(
        "rag_evaluation_rounds",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("owner_marker", sa.String(length=64), nullable=False),
        sa.Column("run_token", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("round_token", postgresql.UUID(as_uuid=True), nullable=False, unique=True),
        sa.Column("round_format", sa.String(length=32), nullable=False),
        sa.Column("doc_keys_json", postgresql.JSONB(), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False, server_default="claimed"),
        sa.Column("state_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("expected_rollout_version", sa.Integer(), nullable=False),
        sa.Column("next_document_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_step", sa.String(length=32), nullable=False, server_default="preflight"),
        sa.Column("attempt_doc_key", sa.String(length=64)),
        sa.Column("expected_source_checksum", sa.String(length=64)),
        sa.Column("reservation_at", sa.DateTime(timezone=True)),
        sa.Column("claimed_job_id", postgresql.UUID(as_uuid=True)),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("pre_state_proof_json", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("post_state_proof_json", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("head_mappings_json", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("immutable_counts_json", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("failure_code", sa.String(length=64)),
        sa.Column("safe_message", sa.String(length=200)),
        sa.Column("terminal_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "tenant_id = '64300000-0000-4000-8000-000000000001'::uuid",
            name="ck_rag_evaluation_rounds_fixed_tenant",
        ),
        sa.CheckConstraint(
            "owner_marker = 'moca.rag_format_parity.v1'",
            name="ck_rag_evaluation_rounds_owner_marker",
        ),
        sa.CheckConstraint(
            "round_format IN ('markdown', 'digital_pdf', 'scanned_pdf')",
            name="ck_rag_evaluation_rounds_format",
        ),
        sa.CheckConstraint(
            f"doc_keys_json = '{_DOC_KEYS_JSON}'::jsonb",
            name="ck_rag_evaluation_rounds_doc_keys",
        ),
        sa.CheckConstraint(
            "state IN ('claimed', 'ingesting', 'retrieving', 'cleaning', 'expired', 'completed', 'abandoned')",
            name="ck_rag_evaluation_rounds_state",
        ),
        sa.CheckConstraint(
            "next_step IN ('preflight', 'ingest', 'retrieve', 'cleanup', 'done')",
            name="ck_rag_evaluation_rounds_next_step",
        ),
        sa.CheckConstraint("state_version > 0", name="ck_rag_evaluation_rounds_state_version_positive"),
        sa.CheckConstraint(
            "expected_rollout_version > 0",
            name="ck_rag_evaluation_rounds_rollout_version_positive",
        ),
        sa.CheckConstraint(
            "next_document_index BETWEEN 0 AND 3",
            name="ck_rag_evaluation_rounds_document_index",
        ),
        sa.CheckConstraint(
            "attempt_doc_key IS NULL OR attempt_doc_key IN "
            "('eval_refund_eligibility_and_return', 'eval_quality_compensation_and_approval', "
            "'eval_cross_border_and_digital_goods')",
            name="ck_rag_evaluation_rounds_attempt_doc_key",
        ),
        sa.CheckConstraint(
            "expected_source_checksum IS NULL OR expected_source_checksum ~ '^[0-9a-f]{64}$'",
            name="ck_rag_evaluation_rounds_source_checksum",
        ),
        sa.CheckConstraint(
            "((attempt_doc_key IS NULL AND expected_source_checksum IS NULL "
            "AND reservation_at IS NULL AND claimed_job_id IS NULL) OR "
            "(attempt_doc_key IS NOT NULL AND expected_source_checksum IS NOT NULL "
            "AND reservation_at IS NOT NULL))",
            name="ck_rag_evaluation_rounds_attempt_reservation",
        ),
        sa.CheckConstraint(
            "((state IN ('completed', 'abandoned') AND terminal_at IS NOT NULL) OR "
            "(state NOT IN ('completed', 'abandoned') AND terminal_at IS NULL))",
            name="ck_rag_evaluation_rounds_terminal",
        ),
    )
    op.create_index(
        "ix_rag_evaluation_rounds_tenant_run",
        "rag_evaluation_rounds",
        ["tenant_id", "run_token"],
    )
    op.create_index(
        "ix_rag_evaluation_rounds_lease",
        "rag_evaluation_rounds",
        ["lease_expires_at"],
    )
    op.create_index(
        "uq_rag_evaluation_rounds_one_active_tenant",
        "rag_evaluation_rounds",
        ["tenant_id"],
        unique=True,
        postgresql_where=sa.text("state NOT IN ('completed', 'abandoned')"),
    )


def downgrade() -> None:
    _assert_downgrade_safe()
    op.drop_index("uq_rag_evaluation_rounds_one_active_tenant", table_name="rag_evaluation_rounds")
    op.drop_index("ix_rag_evaluation_rounds_lease", table_name="rag_evaluation_rounds")
    op.drop_index("ix_rag_evaluation_rounds_tenant_run", table_name="rag_evaluation_rounds")
    op.drop_table("rag_evaluation_rounds")


def _assert_downgrade_safe() -> None:
    active = bool(
        op.get_bind()
        .execute(
            sa.text("SELECT EXISTS (SELECT 1 FROM rag_evaluation_rounds WHERE state NOT IN ('completed', 'abandoned'))")
        )
        .scalar_one()
    )
    if active:
        raise RuntimeError(
            "refusing downgrade: expire, exact-proof, same-owner cleanup, and terminal abandon active rounds first"
        )
