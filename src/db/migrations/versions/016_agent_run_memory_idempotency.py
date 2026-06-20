"""Add agent run memory idempotency indexes.

Revision ID: 016_agent_run_memory_idempotency
Revises: 015_rag_production_ingestion_ocr
Create Date: 2026-06-20
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "016_agent_run_memory_idempotency"
down_revision: str | None = "015_rag_production_ingestion_ocr"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    _ensure_no_run_role_message_duplicates()
    op.create_index(
        "uq_conversation_messages_active_tenant_run_role",
        "conversation_messages",
        ["tenant_id", "run_id", "role"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL AND run_id IS NOT NULL AND role IN ('user', 'assistant')"),
    )

    _ensure_no_thread_rolling_source_end_duplicates()
    op.create_index(
        "uq_summaries_thread_rolling_source_end",
        "summaries",
        ["tenant_id", "conversation_thread_id", "summary_type", "source_end_message_id"],
        unique=True,
        postgresql_where=sa.text(
            "deleted_at IS NULL AND summary_type = 'thread_rolling' AND source_end_message_id IS NOT NULL"
        ),
    )


def downgrade() -> None:
    op.drop_index("uq_summaries_thread_rolling_source_end", table_name="summaries")
    op.drop_index("uq_conversation_messages_active_tenant_run_role", table_name="conversation_messages")


def _ensure_no_run_role_message_duplicates() -> None:
    bind = op.get_bind()
    duplicate = (
        bind.execute(
            sa.text(
                """
                SELECT tenant_id, run_id, role, COUNT(*) AS duplicate_count
                FROM conversation_messages
                WHERE deleted_at IS NULL
                  AND run_id IS NOT NULL
                  AND role IN ('user', 'assistant')
                GROUP BY tenant_id, run_id, role
                HAVING COUNT(*) > 1
                LIMIT 1
                """
            )
        )
        .mappings()
        .first()
    )
    if duplicate is not None:
        raise RuntimeError(
            "Cannot create uq_conversation_messages_active_tenant_run_role: "
            "active conversation_messages contain duplicate tenant_id/run_id/role rows. "
            f"tenant_id={duplicate['tenant_id']} run_id={duplicate['run_id']} "
            f"role={duplicate['role']} duplicate_count={duplicate['duplicate_count']}."
        )


def _ensure_no_thread_rolling_source_end_duplicates() -> None:
    bind = op.get_bind()
    duplicate = (
        bind.execute(
            sa.text(
                """
                SELECT tenant_id, conversation_thread_id, source_end_message_id, COUNT(*) AS duplicate_count
                FROM summaries
                WHERE deleted_at IS NULL
                  AND summary_type = 'thread_rolling'
                  AND source_end_message_id IS NOT NULL
                GROUP BY tenant_id, conversation_thread_id, source_end_message_id
                HAVING COUNT(*) > 1
                LIMIT 1
                """
            )
        )
        .mappings()
        .first()
    )
    if duplicate is not None:
        raise RuntimeError(
            "Cannot create uq_summaries_thread_rolling_source_end: "
            "active thread_rolling summaries contain duplicate tenant_id/conversation_thread_id/"
            "source_end_message_id rows. "
            f"tenant_id={duplicate['tenant_id']} conversation_thread_id={duplicate['conversation_thread_id']} "
            f"source_end_message_id={duplicate['source_end_message_id']} "
            f"duplicate_count={duplicate['duplicate_count']}."
        )
