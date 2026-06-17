"""Scope active conversation thread uniqueness by user.

Revision ID: 012_thread_user_scope
Revises: 011_memory_foundation_v2
Create Date: 2026-06-17
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "012_thread_user_scope"
down_revision: str | None = "011_memory_foundation_v2"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.drop_index("uq_conversation_threads_active_tenant_thread", table_name="conversation_threads")
    op.create_index(
        "uq_conversation_threads_active_tenant_user_thread",
        "conversation_threads",
        ["tenant_id", "user_id", "thread_id"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )


def downgrade() -> None:
    _ensure_no_active_thread_id_duplicates()
    op.drop_index("uq_conversation_threads_active_tenant_user_thread", table_name="conversation_threads")
    op.create_index(
        "uq_conversation_threads_active_tenant_thread",
        "conversation_threads",
        ["tenant_id", "thread_id"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )


def _ensure_no_active_thread_id_duplicates() -> None:
    bind = op.get_bind()
    duplicate = bind.execute(
        sa.text(
            """
            SELECT tenant_id, thread_id, COUNT(*) AS duplicate_count
            FROM conversation_threads
            WHERE deleted_at IS NULL
            GROUP BY tenant_id, thread_id
            HAVING COUNT(*) > 1
            LIMIT 1
            """
        )
    ).mappings().first()
    if duplicate is not None:
        raise RuntimeError(
            "Cannot downgrade 012_thread_user_scope: active conversation_threads contain "
            "multiple users for the same tenant_id/thread_id. Archive, delete, or merge "
            "duplicates before restoring the legacy tenant/thread unique index. "
            f"Example tenant_id={duplicate['tenant_id']} thread_id={duplicate['thread_id']} "
            f"count={duplicate['duplicate_count']}."
        )
