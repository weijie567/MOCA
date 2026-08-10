from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Computed,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class Tenant(TimestampMixin, Base):
    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)

    merchants: Mapped[list["Merchant"]] = relationship(back_populates="tenant")
    users: Mapped[list["User"]] = relationship(back_populates="tenant")


class Role(TimestampMixin, Base):
    __tablename__ = "roles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String(255))

    user_roles: Mapped[list["UserRole"]] = relationship(back_populates="role")


class Merchant(TimestampMixin, Base):
    __tablename__ = "merchants"
    __table_args__ = (UniqueConstraint("id", "tenant_id", name="uq_merchants_id_tenant"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    merchant_name: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str] = mapped_column(String(80), nullable=False)
    risk_level: Mapped[str] = mapped_column(String(32), default="low", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)

    tenant: Mapped["Tenant"] = relationship(back_populates="merchants")
    orders: Mapped[list["Order"]] = relationship(back_populates="merchant")
    users: Mapped[list["User"]] = relationship(
        back_populates="merchant",
        primaryjoin="and_(Merchant.id == User.merchant_id, Merchant.tenant_id == User.tenant_id)",
        foreign_keys="User.merchant_id",
    )


class User(TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("tenant_id", "username", name="uq_users_tenant_username"),
        ForeignKeyConstraint(
            ["merchant_id", "tenant_id"],
            ["merchants.id", "merchants.tenant_id"],
            name="fk_users_merchant_tenant",
        ),
        CheckConstraint(
            "NOT is_active OR role NOT IN ('support', 'manager', 'merchant') OR merchant_id IS NOT NULL",
            name="ck_users_active_business_role_has_merchant",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    merchant_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    username: Mapped[str] = mapped_column(String(120), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    tenant: Mapped["Tenant"] = relationship(back_populates="users")
    merchant: Mapped["Merchant | None"] = relationship(
        back_populates="users",
        primaryjoin="and_(User.merchant_id == Merchant.id, User.tenant_id == Merchant.tenant_id)",
        foreign_keys=[merchant_id],
    )
    user_roles: Mapped[list["UserRole"]] = relationship(back_populates="user")


class UserRole(TimestampMixin, Base):
    __tablename__ = "user_roles"
    __table_args__ = (UniqueConstraint("user_id", "role_id", name="uq_user_roles_user_role"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    role_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("roles.id"), nullable=False, index=True)

    user: Mapped["User"] = relationship(back_populates="user_roles")
    role: Mapped["Role"] = relationship(back_populates="user_roles")


class Order(TimestampMixin, Base):
    __tablename__ = "orders"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    merchant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("merchants.id"), nullable=False, index=True
    )
    order_no: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    buyer_name: Mapped[str] = mapped_column(String(120), nullable=False)
    item_name: Mapped[str] = mapped_column(String(200), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(8), default="CNY", nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    shipped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    merchant: Mapped["Merchant"] = relationship(back_populates="orders")
    refund_cases: Mapped[list["RefundCase"]] = relationship(back_populates="order")
    tickets: Mapped[list["Ticket"]] = relationship(back_populates="order")


class RefundCase(TimestampMixin, Base):
    __tablename__ = "refund_cases"
    __table_args__ = (UniqueConstraint("id", "tenant_id", name="uq_refund_cases_id_tenant"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    order_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("orders.id"), nullable=False, index=True)
    refund_case_no: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    reason_code: Mapped[str] = mapped_column(String(64), nullable=False)
    reason_text: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    requested_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    approved_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))

    order: Mapped["Order"] = relationship(back_populates="refund_cases")
    tickets: Mapped[list["Ticket"]] = relationship(back_populates="refund_case")


class Ticket(TimestampMixin, Base):
    __tablename__ = "tickets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    order_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("orders.id"), nullable=False, index=True)
    refund_case_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("refund_cases.id"))
    ticket_no: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    channel: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    messages: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list, nullable=False)

    order: Mapped["Order"] = relationship(back_populates="tickets")
    refund_case: Mapped["RefundCase | None"] = relationship(back_populates="tickets")


class PolicyDocument(TimestampMixin, Base):
    __tablename__ = "policy_documents"
    __table_args__ = (
        UniqueConstraint("tenant_id", "doc_key", name="uq_policy_documents_tenant_doc_key"),
        UniqueConstraint("id", "tenant_id", name="uq_policy_documents_id_tenant"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    doc_key: Mapped[str] = mapped_column(String(64), nullable=False)
    doc_type: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    risk_level: Mapped[str] = mapped_column(String(32), nullable=False)
    version: Mapped[int] = mapped_column(default=1, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    source_type: Mapped[str | None] = mapped_column(String(32))
    source_checksum: Mapped[str | None] = mapped_column(String(128))
    parser_metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    policy_version_fingerprint: Mapped[str | None] = mapped_column(String(128))
    evidence_write_sequence: Mapped[int | None] = mapped_column(BigInteger)

    chunks: Mapped[list["PolicyChunk"]] = relationship(back_populates="document")
    document_blocks: Mapped[list["DocumentBlock"]] = relationship(back_populates="document")
    ingestion_jobs: Mapped[list["RagIngestionJob"]] = relationship(back_populates="document")


class DocumentBlock(TimestampMixin, Base):
    __tablename__ = "document_blocks"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "doc_id",
            "source_block_id",
            name="uq_document_blocks_tenant_doc_source_block",
        ),
        CheckConstraint("block_index >= 0", name="ck_document_blocks_block_index_nonnegative"),
        CheckConstraint("char_length(text) <= 20000", name="ck_document_blocks_text_max_length"),
        Index("ix_document_blocks_tenant_doc_index", "tenant_id", "doc_id", "block_index"),
        Index("ix_document_blocks_tenant_doc_source_block", "tenant_id", "doc_id", "source_block_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    doc_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("policy_documents.id"), nullable=False, index=True
    )
    source_block_id: Mapped[str] = mapped_column(String(128), nullable=False)
    block_index: Mapped[int] = mapped_column(nullable=False)
    block_type: Mapped[str] = mapped_column(String(32), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_text: Mapped[str] = mapped_column(Text, nullable=False)
    text_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    page_number: Mapped[int | None] = mapped_column()
    bbox_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    table_metadata_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    parser_metadata_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    ocr_metadata_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    source_uri: Mapped[str | None] = mapped_column(String(1024))

    document: Mapped["PolicyDocument"] = relationship(back_populates="document_blocks")


class RagIngestionJob(TimestampMixin, Base):
    __tablename__ = "rag_ingestion_jobs"
    __table_args__ = (
        CheckConstraint(
            "stage IN ('received', 'parsing', 'cleaning', 'chunking', 'embedding', 'persisting', 'completed')",
            name="ck_rag_ingestion_jobs_stage",
        ),
        CheckConstraint(
            "status IN ('pending', 'running', 'success', 'failed')",
            name="ck_rag_ingestion_jobs_status",
        ),
        Index("ix_rag_ingestion_jobs_tenant_doc", "tenant_id", "doc_id"),
        Index("ix_rag_ingestion_jobs_tenant_doc_key", "tenant_id", "doc_key"),
        Index("ix_rag_ingestion_jobs_tenant_status", "tenant_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    doc_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("policy_documents.id"), nullable=True, index=True
    )
    doc_key: Mapped[str] = mapped_column(String(64), nullable=False)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source_checksum: Mapped[str] = mapped_column(String(128), nullable=False)
    parser_name: Mapped[str] = mapped_column(String(64), nullable=False)
    parser_version: Mapped[str] = mapped_column(String(64), nullable=False)
    ocr_engine: Mapped[str | None] = mapped_column(String(64))
    stage: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(64))
    safe_message: Mapped[str | None] = mapped_column(String(500))
    warnings_json: Mapped[list[Any]] = mapped_column(JSONB, default=list, nullable=False)
    counts_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    timings_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    document: Mapped["PolicyDocument"] = relationship(back_populates="ingestion_jobs")


class RagEvaluationRound(TimestampMixin, Base):
    """Evaluation-only durable owner for one format-parity round.

    This row is deliberately independent of the mutable document projection. It
    is the authority that must be locked and CAS-validated before the evaluator
    may inspect or remove any current child rows.
    """

    __tablename__ = "rag_evaluation_rounds"
    __table_args__ = (
        CheckConstraint(
            "tenant_id = '64300000-0000-4000-8000-000000000001'::uuid",
            name="ck_rag_evaluation_rounds_fixed_tenant",
        ),
        CheckConstraint(
            "owner_marker = 'moca.rag_format_parity.v1'",
            name="ck_rag_evaluation_rounds_owner_marker",
        ),
        CheckConstraint(
            "round_format IN ('markdown', 'digital_pdf', 'scanned_pdf')",
            name="ck_rag_evaluation_rounds_format",
        ),
        CheckConstraint(
            'doc_keys_json = \'["eval_refund_eligibility_and_return",'
            '"eval_quality_compensation_and_approval",'
            '"eval_cross_border_and_digital_goods"]\'::jsonb',
            name="ck_rag_evaluation_rounds_doc_keys",
        ),
        CheckConstraint(
            "state IN ('claimed', 'ingesting', 'retrieving', 'cleaning', 'expired', 'completed', 'abandoned')",
            name="ck_rag_evaluation_rounds_state",
        ),
        CheckConstraint(
            "next_step IN ('preflight', 'ingest', 'retrieve', 'cleanup', 'done')",
            name="ck_rag_evaluation_rounds_next_step",
        ),
        CheckConstraint("state_version > 0", name="ck_rag_evaluation_rounds_state_version_positive"),
        CheckConstraint(
            "expected_rollout_version > 0",
            name="ck_rag_evaluation_rounds_rollout_version_positive",
        ),
        CheckConstraint(
            "run_identity_hash ~ '^[0-9a-f]{64}$'",
            name="ck_rag_evaluation_rounds_run_identity_hash",
        ),
        CheckConstraint(
            "next_document_index >= 0 AND next_document_index <= 3",
            name="ck_rag_evaluation_rounds_document_index",
        ),
        CheckConstraint(
            "attempt_doc_key IS NULL OR attempt_doc_key IN "
            "('eval_refund_eligibility_and_return', 'eval_quality_compensation_and_approval', "
            "'eval_cross_border_and_digital_goods')",
            name="ck_rag_evaluation_rounds_attempt_doc_key",
        ),
        CheckConstraint(
            "expected_source_checksum IS NULL OR expected_source_checksum ~ '^[0-9a-f]{64}$'",
            name="ck_rag_evaluation_rounds_source_checksum",
        ),
        CheckConstraint(
            "((attempt_doc_key IS NULL AND expected_source_checksum IS NULL "
            "AND reservation_at IS NULL AND claimed_job_id IS NULL) OR "
            "(attempt_doc_key IS NOT NULL AND expected_source_checksum IS NOT NULL "
            "AND reservation_at IS NOT NULL))",
            name="ck_rag_evaluation_rounds_attempt_reservation",
        ),
        CheckConstraint(
            "((state IN ('completed', 'abandoned') AND terminal_at IS NOT NULL) OR "
            "(state NOT IN ('completed', 'abandoned') AND terminal_at IS NULL))",
            name="ck_rag_evaluation_rounds_terminal",
        ),
        Index("ix_rag_evaluation_rounds_tenant_run", "tenant_id", "run_token"),
        Index("ix_rag_evaluation_rounds_lease", "lease_expires_at"),
        Index(
            "uq_rag_evaluation_rounds_one_active_tenant",
            "tenant_id",
            unique=True,
            postgresql_where=text("state NOT IN ('completed', 'abandoned')"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False
    )
    owner_marker: Mapped[str] = mapped_column(String(64), nullable=False)
    run_token: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    round_token: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, unique=True)
    round_format: Mapped[str] = mapped_column(String(32), nullable=False)
    doc_keys_json: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False, default="claimed", server_default="claimed")
    state_version: Mapped[int] = mapped_column(nullable=False, default=1, server_default=text("1"))
    expected_rollout_version: Mapped[int] = mapped_column(nullable=False)
    run_identity_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    next_document_index: Mapped[int] = mapped_column(nullable=False, default=0, server_default=text("0"))
    next_step: Mapped[str] = mapped_column(String(32), nullable=False, default="preflight", server_default="preflight")
    attempt_doc_key: Mapped[str | None] = mapped_column(String(64))
    expected_source_checksum: Mapped[str | None] = mapped_column(String(64))
    reservation_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    claimed_job_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    lease_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    pre_state_proof_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    post_state_proof_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    head_mappings_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    immutable_counts_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    failure_code: Mapped[str | None] = mapped_column(String(64))
    safe_message: Mapped[str | None] = mapped_column(String(200))
    terminal_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PolicyChunk(TimestampMixin, Base):
    __tablename__ = "policy_chunks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    doc_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("policy_documents.id"), nullable=False, index=True
    )
    chunk_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    section: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    search_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    source_block_refs_json: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list, nullable=False)
    ocr_metadata_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    search_vector: Mapped[str | None] = mapped_column(
        TSVECTOR,
        Computed("to_tsvector('simple', coalesce(search_text, ''))", persisted=True),
    )
    risk_level: Mapped[str] = mapped_column(String(32), nullable=False)
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1024))
    evidence_write_sequence: Mapped[int | None] = mapped_column(BigInteger)

    document: Mapped["PolicyDocument"] = relationship(back_populates="chunks")


_EVIDENCE_SOURCE_LOCATOR_CHECK = (
    "jsonb_typeof(source_locator_json) = 'object' "
    "AND source_locator_json ? 'source_type' "
    "AND (source_locator_json - "
    "ARRAY['source_type', 'source_checksum', 'source_uri', 'page_number', 'source_block_refs']::text[]) "
    "= '{}'::jsonb"
)
_EVIDENCE_LIFECYCLE_CHECK = (
    "lifecycle_status IN ('active', 'superseded', 'corrected', 'archived', 'expired', 'tombstoned')"
)


class PolicyDocumentVersion(TimestampMixin, Base):
    """Append-only retained document material for evidence identity and replay."""

    __tablename__ = "policy_document_versions"
    __table_args__ = (
        UniqueConstraint("id", "tenant_id", name="uq_policy_document_versions_id_tenant"),
        UniqueConstraint(
            "tenant_id",
            "scope_type",
            "scope_id",
            "doc_key",
            "document_version",
            name="uq_policy_document_versions_logical",
        ),
        UniqueConstraint(
            "id",
            "tenant_id",
            "scope_type",
            "scope_id",
            "doc_key",
            "document_version",
            name="uq_policy_document_versions_identity",
        ),
        ForeignKeyConstraint(
            ["policy_document_id", "tenant_id"],
            ["policy_documents.id", "policy_documents.tenant_id"],
            name="fk_policy_document_versions_head_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["supersedes_version_id", "tenant_id"],
            ["policy_document_versions.id", "policy_document_versions.tenant_id"],
            name="fk_policy_document_versions_supersedes_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["corrects_version_id", "tenant_id"],
            ["policy_document_versions.id", "policy_document_versions.tenant_id"],
            name="fk_policy_document_versions_corrects_tenant",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "scope_type = 'tenant_policy' AND scope_id = CAST(tenant_id AS VARCHAR)",
            name="ck_policy_document_versions_tenant_policy_scope",
        ),
        CheckConstraint(
            "document_version > 0",
            name="ck_policy_document_versions_document_version_positive",
        ),
        CheckConstraint(
            "content_hash ~ '^sha256:[0-9a-f]{64}$'",
            name="ck_policy_document_versions_content_hash",
        ),
        CheckConstraint(_EVIDENCE_SOURCE_LOCATOR_CHECK, name="ck_policy_document_versions_source_locator_allowlist"),
        CheckConstraint(_EVIDENCE_LIFECYCLE_CHECK, name="ck_policy_document_versions_lifecycle_status"),
        Index("ix_policy_document_versions_tenant_doc_version", "tenant_id", "doc_key", "document_version"),
        Index("ix_policy_document_versions_retention", "retention_until"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    policy_document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    scope_type: Mapped[str] = mapped_column(String(32), nullable=False)
    scope_id: Mapped[str] = mapped_column(String(64), nullable=False)
    doc_key: Mapped[str] = mapped_column(String(64), nullable=False)
    document_version: Mapped[int] = mapped_column(nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(71), nullable=False)
    source_locator_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    lifecycle_status: Mapped[str] = mapped_column(String(32), default="active", server_default="active", nullable=False)
    retention_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    tombstoned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    supersedes_version_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    corrects_version_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))


class PolicyChunkVersion(TimestampMixin, Base):
    """Append-only retained chunk material bound to one exact document version."""

    __tablename__ = "policy_chunk_versions"
    __table_args__ = (
        UniqueConstraint("id", "tenant_id", name="uq_policy_chunk_versions_id_tenant"),
        UniqueConstraint(
            "id",
            "tenant_id",
            "policy_document_version_id",
            name="uq_policy_chunk_versions_id_tenant_document",
        ),
        UniqueConstraint(
            "tenant_id",
            "scope_type",
            "scope_id",
            "doc_key",
            "document_version",
            "chunk_id",
            "chunk_version",
            name="uq_policy_chunk_versions_identity",
        ),
        ForeignKeyConstraint(
            [
                "policy_document_version_id",
                "tenant_id",
                "scope_type",
                "scope_id",
                "doc_key",
                "document_version",
            ],
            [
                "policy_document_versions.id",
                "policy_document_versions.tenant_id",
                "policy_document_versions.scope_type",
                "policy_document_versions.scope_id",
                "policy_document_versions.doc_key",
                "policy_document_versions.document_version",
            ],
            name="fk_policy_chunk_versions_document_identity",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["supersedes_version_id", "tenant_id"],
            ["policy_chunk_versions.id", "policy_chunk_versions.tenant_id"],
            name="fk_policy_chunk_versions_supersedes_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["corrects_version_id", "tenant_id"],
            ["policy_chunk_versions.id", "policy_chunk_versions.tenant_id"],
            name="fk_policy_chunk_versions_corrects_tenant",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "scope_type = 'tenant_policy' AND scope_id = CAST(tenant_id AS VARCHAR)",
            name="ck_policy_chunk_versions_tenant_policy_scope",
        ),
        CheckConstraint(
            "document_version > 0 AND chunk_version > 0",
            name="ck_policy_chunk_versions_versions_positive",
        ),
        CheckConstraint(
            "text_hash ~ '^sha256:[0-9a-f]{64}$'",
            name="ck_policy_chunk_versions_text_hash",
        ),
        CheckConstraint(_EVIDENCE_SOURCE_LOCATOR_CHECK, name="ck_policy_chunk_versions_source_locator_allowlist"),
        CheckConstraint(_EVIDENCE_LIFECYCLE_CHECK, name="ck_policy_chunk_versions_lifecycle_status"),
        Index(
            "ix_policy_chunk_versions_tenant_chunk_version",
            "tenant_id",
            "doc_key",
            "chunk_id",
            "document_version",
            "chunk_version",
        ),
        Index("ix_policy_chunk_versions_retention", "retention_until"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    policy_document_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    scope_type: Mapped[str] = mapped_column(String(32), nullable=False)
    scope_id: Mapped[str] = mapped_column(String(64), nullable=False)
    doc_key: Mapped[str] = mapped_column(String(64), nullable=False)
    document_version: Mapped[int] = mapped_column(nullable=False)
    chunk_id: Mapped[str] = mapped_column(String(64), nullable=False)
    chunk_version: Mapped[int] = mapped_column(nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    text_hash: Mapped[str] = mapped_column(String(71), nullable=False)
    source_locator_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    lifecycle_status: Mapped[str] = mapped_column(String(32), default="active", server_default="active", nullable=False)
    retention_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    tombstoned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    supersedes_version_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    corrects_version_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))


class EvidenceSnapshotDependency(TimestampMixin, Base):
    """Normalized retained event-to-immutable-evidence dependency."""

    __tablename__ = "evidence_snapshot_dependencies"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "event_id",
            "document_version_id",
            "chunk_version_id",
            name="uq_evidence_snapshot_dependencies_binding",
        ),
        ForeignKeyConstraint(
            ["event_id", "tenant_id"],
            ["agent_trace_events.event_id", "agent_trace_events.tenant_id"],
            name="fk_evidence_snapshot_dependencies_event_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["document_version_id", "tenant_id"],
            ["policy_document_versions.id", "policy_document_versions.tenant_id"],
            name="fk_evidence_snapshot_dependencies_document_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["chunk_version_id", "tenant_id", "document_version_id"],
            [
                "policy_chunk_versions.id",
                "policy_chunk_versions.tenant_id",
                "policy_chunk_versions.policy_document_version_id",
            ],
            name="fk_evidence_snapshot_dependencies_chunk_tenant_document",
            ondelete="RESTRICT",
        ),
        Index("ix_evidence_snapshot_dependencies_tenant_event", "tenant_id", "event_id"),
        Index("ix_evidence_snapshot_dependencies_retention", "retention_until"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    document_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    chunk_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    retention_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class EvidenceIdentityRollout(TimestampMixin, Base):
    """Singleton CAS/lock row for staged evidence identity rollout."""

    __tablename__ = "evidence_identity_rollouts"
    __table_args__ = (
        CheckConstraint("id = 1", name="ck_evidence_identity_rollouts_singleton"),
        CheckConstraint("rollout_version >= 0", name="ck_evidence_identity_rollouts_version_nonnegative"),
        CheckConstraint(
            "backfill_watermark_sequence IS NULL OR backfill_watermark_sequence >= 0",
            name="ck_evidence_identity_rollouts_watermark_nonnegative",
        ),
        CheckConstraint(
            "reconciled_through_sequence IS NULL OR reconciled_through_sequence >= 0",
            name="ck_evidence_identity_rollouts_reconciled_nonnegative",
        ),
        CheckConstraint(
            "NOT canonical_reads_enabled OR dual_write_enabled_at IS NOT NULL",
            name="ck_evidence_identity_rollouts_reads_require_dual_write",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, default=1, server_default=text("1"))
    rollout_version: Mapped[int] = mapped_column(default=0, server_default=text("0"), nullable=False)
    dual_write_enabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    backfill_watermark_sequence: Mapped[int | None] = mapped_column(BigInteger)
    reconciled_through_sequence: Mapped[int | None] = mapped_column(BigInteger)
    canonical_reads_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default=text("false"),
        nullable=False,
    )
    canonical_reads_enabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    canonical_reads_disabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    quarantine_reason: Mapped[str | None] = mapped_column(String(500))
    audit_counts_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        server_default=text("'{}'::jsonb"),
        nullable=False,
    )


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    role: Mapped[str | None] = mapped_column(String(32))
    action: Mapped[str] = mapped_column(String(120), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    trace_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    tool_call_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    run_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    latency_ms: Mapped[int] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(64))
    idempotency_key: Mapped[str | None] = mapped_column(String(128))
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class AgentRun(TimestampMixin, Base):
    """One row per graph.ainvoke() call. Records run-level trace. Per D-05b."""

    __tablename__ = "agent_runs"
    __table_args__ = (
        CheckConstraint(
            "scope_classification IN ('business_merchant', 'policy_only', 'merchant_not_required', 'unknown_legacy')",
            name="ck_agent_runs_scope_classification",
        ),
        CheckConstraint(
            "((scope_classification = 'business_merchant' "
            "AND target_merchant_id IS NOT NULL AND target_merchant_ref IS NOT NULL) "
            "OR (scope_classification IN ('policy_only', 'merchant_not_required', 'unknown_legacy') "
            "AND target_merchant_id IS NULL AND target_merchant_ref IS NULL))",
            name="ck_agent_runs_scope_target_consistency",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    thread_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    input_query: Mapped[str] = mapped_column(Text, nullable=False)
    final_status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    # "completed" | "error" | "insufficient_evidence"
    final_response: Mapped[str | None] = mapped_column(Text)
    target_merchant_id: Mapped[str | None] = mapped_column(String(128))
    target_merchant_ref: Mapped[dict[str, Any] | None] = mapped_column(JSONB(none_as_null=True))
    scope_classification: Mapped[str] = mapped_column(String(32), nullable=False, default="unknown_legacy")
    scope_source: Mapped[str | None] = mapped_column(String(64))
    scope_reason_codes: Mapped[list[str] | None] = mapped_column(JSONB)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    total_latency_ms: Mapped[int | None] = mapped_column()
    total_tokens: Mapped[int | None] = mapped_column()
    total_cost: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))
    error_summary: Mapped[str | None] = mapped_column(String(500))

    steps: Mapped[list["AgentStep"]] = relationship(back_populates="run", cascade="all, delete-orphan")
    trace_events: Mapped[list["AgentTraceEvent"]] = relationship(back_populates="run", cascade="all, delete-orphan")


Index("ix_agent_runs_tenant_target_merchant", AgentRun.tenant_id, AgentRun.target_merchant_id)
Index("ix_agent_runs_tenant_scope_classification", AgentRun.tenant_id, AgentRun.scope_classification)


class SessionMemory(TimestampMixin, Base):
    __tablename__ = "session_memories"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    thread_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    schema_version: Mapped[str] = mapped_column(String(48), nullable=False, default="session_memory.v2")
    active_slots_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    session_summary: Mapped[str | None] = mapped_column(Text)
    unresolved_questions_json: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    last_intent: Mapped[str | None] = mapped_column(String(64))
    last_business_context_refs_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    last_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_runs.id"), nullable=True, index=True
    )
    version: Mapped[int] = mapped_column(default=1, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


Index(
    "uq_session_memories_active_scope",
    SessionMemory.tenant_id,
    SessionMemory.user_id,
    SessionMemory.thread_id,
    unique=True,
    postgresql_where=SessionMemory.deleted_at.is_(None),
)
Index("ix_session_memories_scope", SessionMemory.tenant_id, SessionMemory.user_id, SessionMemory.thread_id)
Index("ix_session_memories_expires_at", SessionMemory.expires_at)


MEMORY_SCOPE_CHECK = "scope_type IN ('tenant', 'merchant', 'user', 'thread', 'case')"
MEMORY_REVIEW_STATUS_CHECK = (
    "review_status IN ('auto_approved', 'needs_review', 'approved', 'rejected', 'superseded', 'tombstoned', 'deleted')"
)
MEMORY_PII_CLASSIFICATION_CHECK = "pii_classification IN ('none', 'low', 'sensitive', 'prohibited')"


class LongTermMemory(TimestampMixin, Base):
    __tablename__ = "long_term_memories"
    __table_args__ = (
        CheckConstraint(MEMORY_SCOPE_CHECK, name="ck_long_term_memories_scope_type"),
        CheckConstraint(
            "memory_kind IN ('fact', 'preference', 'constraint', 'pattern')",
            name="ck_long_term_memories_memory_kind",
        ),
        CheckConstraint(MEMORY_REVIEW_STATUS_CHECK, name="ck_long_term_memories_review_status"),
        CheckConstraint(MEMORY_PII_CLASSIFICATION_CHECK, name="ck_long_term_memories_pii_classification"),
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_long_term_memories_confidence_range"),
        CheckConstraint("version > 0", name="ck_long_term_memories_version_positive"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    schema_version: Mapped[str] = mapped_column(String(48), nullable=False, default="long_term_memory.v2")
    scope_type: Mapped[str] = mapped_column(String(32), nullable=False)
    scope_id: Mapped[str] = mapped_column(String(128), nullable=False)
    memory_kind: Mapped[str] = mapped_column(String(64), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_ref_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    source_identity_hash: Mapped[str | None] = mapped_column(String(80))
    confidence: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    pii_classification: Mapped[str] = mapped_column(String(32), nullable=False, default="none")
    review_status: Mapped[str] = mapped_column(String(32), nullable=False, default="needs_review")
    version: Mapped[int] = mapped_column(default=1, nullable=False)
    supersedes: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("long_term_memories.id"))
    superseded_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("long_term_memories.id"))
    superseded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by_run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("agent_runs.id"))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


Index(
    "uq_long_term_memories_active_identity",
    LongTermMemory.tenant_id,
    LongTermMemory.scope_type,
    LongTermMemory.scope_id,
    LongTermMemory.content_hash,
    unique=True,
    postgresql_where=text("deleted_at IS NULL AND is_current IS TRUE"),
)
Index(
    "ix_long_term_memories_active_retrieval",
    LongTermMemory.tenant_id,
    LongTermMemory.scope_type,
    LongTermMemory.scope_id,
    LongTermMemory.review_status,
    LongTermMemory.is_current,
    LongTermMemory.expires_at,
    postgresql_where=text("deleted_at IS NULL"),
)
Index(
    "ix_long_term_memories_source_identity",
    LongTermMemory.tenant_id,
    LongTermMemory.scope_type,
    LongTermMemory.scope_id,
    LongTermMemory.source_identity_hash,
    postgresql_where=text("source_identity_hash IS NOT NULL AND deleted_at IS NULL"),
)


class CaseMemory(TimestampMixin, Base):
    __tablename__ = "case_memories"
    __table_args__ = (
        UniqueConstraint("id", "tenant_id", name="uq_case_memories_id_tenant"),
        ForeignKeyConstraint(
            ["corrects_case_memory_id", "tenant_id"],
            ["case_memories.id", "case_memories.tenant_id"],
            name="fk_case_memories_corrects_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["supersedes_case_memory_id", "tenant_id"],
            ["case_memories.id", "case_memories.tenant_id"],
            name="fk_case_memories_supersedes_tenant",
            ondelete="RESTRICT",
        ),
        CheckConstraint(MEMORY_SCOPE_CHECK, name="ck_case_memories_scope_type"),
        CheckConstraint(MEMORY_REVIEW_STATUS_CHECK, name="ck_case_memories_review_status"),
        CheckConstraint(MEMORY_PII_CLASSIFICATION_CHECK, name="ck_case_memories_pii_classification"),
        CheckConstraint(
            "identity_resolution_status IN ('canonical', 'legacy_resolved', 'legacy_unresolved')",
            name="ck_case_memories_identity_resolution_status",
        ),
        CheckConstraint("lifecycle_version > 0", name="ck_case_memories_lifecycle_version_positive"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    schema_version: Mapped[str] = mapped_column(String(48), nullable=False, default="case_memory.v2")
    scope_type: Mapped[str] = mapped_column(String(32), nullable=False)
    scope_id: Mapped[str] = mapped_column(String(128), nullable=False)
    case_type: Mapped[str] = mapped_column(String(64), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    excerpt: Mapped[str] = mapped_column(Text, nullable=False)
    applicability: Mapped[str | None] = mapped_column(Text)
    outcome: Mapped[str | None] = mapped_column(Text)
    caveats: Mapped[str | None] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    policy_family: Mapped[str | None] = mapped_column(String(80))
    policy_version: Mapped[str | None] = mapped_column(String(80))
    policy_refs_json: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    source_ref_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    source_identity_hash: Mapped[str | None] = mapped_column(String(80))
    identity_algorithm_version: Mapped[str | None] = mapped_column(String(64))
    candidate_hash: Mapped[str | None] = mapped_column(String(80))
    identity_resolution_status: Mapped[str] = mapped_column(String(32), nullable=False)
    provenance_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    lifecycle_version: Mapped[int] = mapped_column(nullable=False, default=1)
    corrects_case_memory_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    supersedes_case_memory_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1024))
    review_status: Mapped[str] = mapped_column(String(32), nullable=False, default="needs_review")
    reviewed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_reason: Mapped[str | None] = mapped_column(Text)
    pii_classification: Mapped[str] = mapped_column(String(32), nullable=False, default="none")
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by_run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("agent_runs.id"))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CaseMemoryIdentityClaim(TimestampMixin, Base):
    """Durable no-resurrection authority for one exact case-memory identity."""

    __tablename__ = "case_memory_identity_claims"
    __table_args__ = (
        UniqueConstraint(
            "identity_algorithm_version",
            "tenant_id",
            "scope_type",
            "scope_id",
            "candidate_hash",
            "content_hash",
            "source_identity_hash",
            name="uq_case_memory_identity_claims_exact_identity",
        ),
        UniqueConstraint(
            "tenant_id",
            "owner_case_memory_id",
            name="uq_case_memory_identity_claims_owner",
        ),
        ForeignKeyConstraint(
            ["owner_case_memory_id", "tenant_id"],
            ["case_memories.id", "case_memories.tenant_id"],
            name="fk_case_memory_identity_claims_owner_tenant",
            ondelete="RESTRICT",
        ),
        CheckConstraint(MEMORY_SCOPE_CHECK, name="ck_case_memory_identity_claims_scope_type"),
        CheckConstraint(
            "candidate_hash ~ '^sha256:[0-9a-f]{64}$' "
            "AND content_hash ~ '^sha256:[0-9a-f]{64}$' "
            "AND source_identity_hash ~ '^sha256:[0-9a-f]{64}$'",
            name="ck_case_memory_identity_claims_hashes",
        ),
        CheckConstraint(
            "claim_state IN ('active', 'terminal')",
            name="ck_case_memory_identity_claims_state",
        ),
        CheckConstraint(
            "((claim_state = 'active' AND terminal_status IS NULL "
            "AND terminal_reason IS NULL AND terminal_at IS NULL) OR "
            "(claim_state = 'terminal' "
            "AND terminal_status IN ('rejected', 'superseded', 'deleted', 'tombstoned') "
            "AND terminal_reason IS NOT NULL AND terminal_at IS NOT NULL))",
            name="ck_case_memory_identity_claims_terminal_fields",
        ),
        CheckConstraint(
            "lifecycle_version > 0",
            name="ck_case_memory_identity_claims_lifecycle_version_positive",
        ),
        Index("ix_case_memory_identity_claims_owner", "tenant_id", "owner_case_memory_id"),
        Index("ix_case_memory_identity_claims_state", "tenant_id", "claim_state"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    identity_algorithm_version: Mapped[str] = mapped_column(String(64), nullable=False)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False
    )
    scope_type: Mapped[str] = mapped_column(String(32), nullable=False)
    scope_id: Mapped[str] = mapped_column(String(128), nullable=False)
    candidate_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    source_identity_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    owner_case_memory_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    claim_state: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    terminal_status: Mapped[str | None] = mapped_column(String(32))
    terminal_reason: Mapped[str | None] = mapped_column(String(128))
    terminal_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lifecycle_version: Mapped[int] = mapped_column(nullable=False, default=1)


Index(
    "ix_case_memories_metadata_filters",
    CaseMemory.tenant_id,
    CaseMemory.scope_type,
    CaseMemory.scope_id,
    CaseMemory.case_type,
    CaseMemory.policy_family,
    CaseMemory.policy_version,
    CaseMemory.review_status,
    CaseMemory.expires_at,
    postgresql_where=text("deleted_at IS NULL"),
)
Index(
    "ix_case_memories_active_content_identity",
    CaseMemory.tenant_id,
    CaseMemory.scope_type,
    CaseMemory.scope_id,
    CaseMemory.content_hash,
    postgresql_where=text("deleted_at IS NULL"),
)
Index(
    "ix_case_memories_source_identity",
    CaseMemory.tenant_id,
    CaseMemory.scope_type,
    CaseMemory.scope_id,
    CaseMemory.source_identity_hash,
    postgresql_where=text("source_identity_hash IS NOT NULL AND deleted_at IS NULL"),
)
Index(
    "ix_case_memories_active_exact_identity",
    CaseMemory.identity_algorithm_version,
    CaseMemory.tenant_id,
    CaseMemory.scope_type,
    CaseMemory.scope_id,
    CaseMemory.candidate_hash,
    CaseMemory.content_hash,
    CaseMemory.source_identity_hash,
    postgresql_where=text(
        "deleted_at IS NULL "
        "AND identity_resolution_status IN ('canonical', 'legacy_resolved') "
        "AND review_status IN ('auto_approved', 'needs_review', 'approved')"
    ),
)
Index(
    "ix_case_memories_embedding_hnsw",
    CaseMemory.embedding,
    postgresql_using="hnsw",
    postgresql_ops={"embedding": "vector_cosine_ops"},
    postgresql_with={"m": 16, "ef_construction": 128},
)


class CaseMemoryLineageLink(TimestampMixin, Base):
    __tablename__ = "case_memory_lineage_links"
    __table_args__ = (
        ForeignKeyConstraint(
            ["survivor_case_memory_id", "tenant_id"],
            ["case_memories.id", "case_memories.tenant_id"],
            name="fk_case_memory_lineage_survivor_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["related_case_memory_id", "tenant_id"],
            ["case_memories.id", "case_memories.tenant_id"],
            name="fk_case_memory_lineage_related_tenant",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "tenant_id",
            "survivor_case_memory_id",
            "related_case_memory_id",
            "relation",
            name="uq_case_memory_lineage_pair_relation",
        ),
        UniqueConstraint(
            "tenant_id",
            "survivor_case_memory_id",
            "relation",
            "ordinal",
            name="uq_case_memory_lineage_survivor_relation_ordinal",
        ),
        CheckConstraint(
            "survivor_case_memory_id <> related_case_memory_id",
            name="ck_case_memory_lineage_distinct_nodes",
        ),
        CheckConstraint(
            "relation IN ('duplicate', 'correction', 'supersession')",
            name="ck_case_memory_lineage_relation",
        ),
        CheckConstraint("ordinal > 0", name="ck_case_memory_lineage_ordinal_positive"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    survivor_case_memory_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    related_case_memory_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    relation: Mapped[str] = mapped_column(String(32), nullable=False)
    ordinal: Mapped[int] = mapped_column(nullable=False)


Index(
    "ix_case_memory_lineage_survivor",
    CaseMemoryLineageLink.tenant_id,
    CaseMemoryLineageLink.survivor_case_memory_id,
    CaseMemoryLineageLink.relation,
    CaseMemoryLineageLink.ordinal,
)


class CaseWorkingContext(TimestampMixin, Base):
    __tablename__ = "case_working_contexts"
    __table_args__ = (
        ForeignKeyConstraint(
            ["case_id", "tenant_id"],
            ["refund_cases.id", "refund_cases.tenant_id"],
            name="fk_case_working_contexts_case_tenant",
        ),
        UniqueConstraint("id", "tenant_id", name="uq_case_working_contexts_id_tenant"),
        CheckConstraint(
            "authority_class = 'contextual_only'",
            name="ck_case_working_contexts_authority_class",
        ),
        CheckConstraint("version > 0", name="ck_case_working_contexts_version_positive"),
        CheckConstraint(MEMORY_PII_CLASSIFICATION_CHECK, name="ck_case_working_contexts_pii_classification"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    case_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("refund_cases.id"), nullable=False)
    schema_version: Mapped[str] = mapped_column(
        String(48), nullable=False, default="case_working_context.v1", server_default="case_working_context.v1"
    )
    authority_class: Mapped[str] = mapped_column(
        String(32), nullable=False, default="contextual_only", server_default="contextual_only"
    )
    customer_request: Mapped[str | None] = mapped_column(Text)
    issue_type: Mapped[str | None] = mapped_column(String(64))
    claims_json: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    verified_facts_json: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    missing_info_json: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    evidence_refs_json: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    actions_taken_json: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    policy_refs_json: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    agent_recommendations_json: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    pending_tasks_json: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    commitments_json: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    next_action_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    source_ref_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    version: Mapped[int] = mapped_column(default=1, server_default="1", nullable=False)
    updated_by_run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("agent_runs.id"))
    pii_classification: Mapped[str] = mapped_column(String(32), nullable=False, default="none", server_default="none")
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


Index("ix_case_working_contexts_tenant_id", CaseWorkingContext.tenant_id)
Index(
    "uq_case_working_contexts_active_scope",
    CaseWorkingContext.tenant_id,
    CaseWorkingContext.case_id,
    unique=True,
    postgresql_where=CaseWorkingContext.deleted_at.is_(None),
)


class CaseWorkingContextRevision(Base):
    __tablename__ = "case_working_context_revisions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["case_working_context_id", "tenant_id"],
            ["case_working_contexts.id", "case_working_contexts.tenant_id"],
            name="fk_cwc_revisions_context_tenant",
        ),
        ForeignKeyConstraint(
            ["case_id", "tenant_id"],
            ["refund_cases.id", "refund_cases.tenant_id"],
            name="fk_cwc_revisions_case_tenant",
        ),
        CheckConstraint(
            "edit_source IN ('run_auto', 'staff_manual')",
            name="ck_cwc_revisions_edit_source",
        ),
        CheckConstraint("version > 0", name="ck_cwc_revisions_version_positive"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    case_working_context_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("case_working_contexts.id"), nullable=False
    )
    case_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("refund_cases.id"), nullable=False)
    version: Mapped[int] = mapped_column(nullable=False)
    snapshot_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    edit_source: Mapped[str] = mapped_column(String(32), nullable=False)
    updated_by_run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("agent_runs.id"))
    source_ref_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


Index(
    "uq_cwc_revisions_context_version",
    CaseWorkingContextRevision.tenant_id,
    CaseWorkingContextRevision.case_working_context_id,
    CaseWorkingContextRevision.version,
    unique=True,
)
Index(
    "ix_cwc_revisions_case",
    CaseWorkingContextRevision.tenant_id,
    CaseWorkingContextRevision.case_id,
    CaseWorkingContextRevision.version,
)


class MemoryTombstone(TimestampMixin, Base):
    __tablename__ = "memory_tombstones"
    __table_args__ = (
        CheckConstraint(MEMORY_SCOPE_CHECK, name="ck_memory_tombstones_scope_type"),
        CheckConstraint(
            "memory_type IN ('long_term_fact', 'case_memory')",
            name="ck_memory_tombstones_memory_type",
        ),
        CheckConstraint(
            "content_hash IS NOT NULL OR source_identity_hash IS NOT NULL",
            name="ck_memory_tombstones_identity_present",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    schema_version: Mapped[str] = mapped_column(String(48), nullable=False, default="memory_tombstone.v1")
    memory_type: Mapped[str] = mapped_column(String(32), nullable=False)
    scope_type: Mapped[str] = mapped_column(String(32), nullable=False)
    scope_id: Mapped[str] = mapped_column(String(128), nullable=False)
    content_hash: Mapped[str | None] = mapped_column(String(80))
    source_ref_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    source_identity_hash: Mapped[str | None] = mapped_column(String(80))
    reason_code: Mapped[str] = mapped_column(String(64), nullable=False)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_by_run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("agent_runs.id"))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


Index(
    "ix_memory_tombstones_active_content_identity",
    MemoryTombstone.tenant_id,
    MemoryTombstone.memory_type,
    MemoryTombstone.scope_type,
    MemoryTombstone.scope_id,
    MemoryTombstone.content_hash,
    unique=True,
    postgresql_where=text("content_hash IS NOT NULL AND deleted_at IS NULL"),
)
Index(
    "ix_memory_tombstones_active_source_identity",
    MemoryTombstone.tenant_id,
    MemoryTombstone.memory_type,
    MemoryTombstone.scope_type,
    MemoryTombstone.scope_id,
    MemoryTombstone.source_identity_hash,
    postgresql_where=text("source_identity_hash IS NOT NULL AND deleted_at IS NULL"),
)
Index(
    "ix_memory_tombstones_active_scope",
    MemoryTombstone.tenant_id,
    MemoryTombstone.memory_type,
    MemoryTombstone.scope_type,
    MemoryTombstone.scope_id,
    postgresql_where=text("deleted_at IS NULL"),
)


class MemoryWriteEvent(Base):
    __tablename__ = "memory_write_events"
    __table_args__ = (
        CheckConstraint(
            "memory_type IN ('session_slot', 'long_term_fact', 'case_memory', 'case_working_context', 'none')",
            name="ck_memory_write_events_memory_type",
        ),
        CheckConstraint(
            "decision IN ('write', 'skip', 'needs_review', 'delete', 'supersede', 'tombstone', 'write_blocked')",
            name="ck_memory_write_events_decision",
        ),
        CheckConstraint(MEMORY_PII_CLASSIFICATION_CHECK, name="ck_memory_write_events_pii_classification"),
        CheckConstraint(
            "(memory_type = 'none' AND memory_id IS NULL) OR memory_type != 'none'",
            name="ck_memory_write_events_none_has_no_memory_id",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("agent_runs.id"), nullable=False)
    memory_type: Mapped[str] = mapped_column(String(32), nullable=False)
    memory_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    schema_version: Mapped[str] = mapped_column(
        String(48), nullable=False, default="memory_write_event.v3", server_default="memory_write_event.v3"
    )
    decision: Mapped[str] = mapped_column(String(32), nullable=False)
    reason_code: Mapped[str] = mapped_column(String(64), nullable=False)
    policy_version: Mapped[str] = mapped_column(
        String(64), nullable=False, default="memory_write_policy.v1", server_default="memory_write_policy.v1"
    )
    blocked_by_json: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    authority_class: Mapped[str] = mapped_column(
        String(32), nullable=False, default="contextual_only", server_default="contextual_only"
    )
    pii_classification: Mapped[str] = mapped_column(String(32), nullable=False)
    candidate_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    source_ref_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


Index("ix_memory_write_events_tenant_run", MemoryWriteEvent.tenant_id, MemoryWriteEvent.run_id)
Index("ix_memory_write_events_memory", MemoryWriteEvent.memory_type, MemoryWriteEvent.memory_id)
Index("ix_memory_write_events_candidate_hash", MemoryWriteEvent.tenant_id, MemoryWriteEvent.candidate_hash)


class ActionSafetySnapshot(Base):
    __tablename__ = "action_safety_snapshots"
    __table_args__ = (UniqueConstraint("tenant_id", "immutable_hash", name="uq_action_safety_snapshots_tenant_hash"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    schema_version: Mapped[str] = mapped_column(String(48), nullable=False, default="action_safety_snapshot.v1")
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("agent_runs.id"), nullable=False)
    snapshot_ref: Mapped[str] = mapped_column(String(128), nullable=False)
    snapshot_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    immutable_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    action_payload_hash: Mapped[str | None] = mapped_column(String(128))
    target_merchant_id: Mapped[str | None] = mapped_column(String(128))
    target_merchant_ref: Mapped[dict[str, Any] | None] = mapped_column(JSONB(none_as_null=True))
    business_fact_refs: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB)
    policy_config_version: Mapped[str] = mapped_column(String(64), nullable=False)
    risk_config_version: Mapped[str] = mapped_column(String(64), nullable=False)
    retrieval_config_version: Mapped[str] = mapped_column(String(64), nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retention_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    run: Mapped["AgentRun"] = relationship()


Index("ix_action_safety_snapshots_tenant_id", ActionSafetySnapshot.tenant_id)
Index("ix_action_safety_snapshots_run_id", ActionSafetySnapshot.run_id)
Index("ix_action_safety_snapshots_tenant_hash", ActionSafetySnapshot.tenant_id, ActionSafetySnapshot.immutable_hash)
Index(
    "ix_action_safety_snapshots_tenant_target_merchant",
    ActionSafetySnapshot.tenant_id,
    ActionSafetySnapshot.target_merchant_id,
)


class ApprovalRequest(TimestampMixin, Base):
    __tablename__ = "approval_requests"
    __table_args__ = (
        UniqueConstraint("tenant_id", "run_id", "revision", name="uq_approval_requests_tenant_run_revision"),
        CheckConstraint(
            "status IN ('pending', 'needs_info', 'approved', 'rejected', 'cancelled', 'expired', 'superseded')",
            name="ck_approval_requests_status",
        ),
        CheckConstraint(
            "resume_attempt_status IS NULL OR "
            "resume_attempt_status IN ('attempted', 'completed', 'failed', 'abandoned')",
            name="ck_approval_requests_resume_attempt_status",
        ),
        CheckConstraint(
            "(resume_attempt_status IS NULL AND resume_attempt_id IS NULL "
            "AND resume_attempt_decision_id IS NULL AND resume_attempt_started_at IS NULL "
            "AND resume_attempt_updated_at IS NULL AND resume_lease_expires_at IS NULL) OR "
            "(resume_attempt_status IS NOT NULL AND resume_attempt_id IS NOT NULL "
            "AND resume_attempt_decision_id IS NOT NULL AND resume_attempt_started_at IS NOT NULL "
            "AND resume_attempt_updated_at IS NOT NULL)",
            name="ck_approval_requests_resume_attempt_identity",
        ),
        CheckConstraint(
            "resume_attempt_status <> 'attempted' OR resume_lease_expires_at IS NOT NULL",
            name="ck_approval_requests_resume_attempt_lease",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_runs.id"), nullable=False, index=True
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    schema_version: Mapped[str | None] = mapped_column(String(48), default="approval_request.v2")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    approval_policy_id: Mapped[str | None] = mapped_column(String(64))
    policy_version: Mapped[str | None] = mapped_column(String(64))
    revision: Mapped[int | None] = mapped_column()
    version: Mapped[int | None] = mapped_column(default=1)
    action_payload_hash: Mapped[str | None] = mapped_column(String(128))
    safety_snapshot_ref: Mapped[str | None] = mapped_column(String(128))
    safety_snapshot_hash: Mapped[str | None] = mapped_column(String(128))
    target_merchant_id: Mapped[str | None] = mapped_column(String(128))
    target_merchant_ref: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    business_fact_refs: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB)
    verified_evidence_refs: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB)
    claim_verification_ref: Mapped[str | None] = mapped_column(String(128))
    claim_verification_summary: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    risk_decision_ref: Mapped[str | None] = mapped_column(String(128))
    risk_decision: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    approval_idempotency_key: Mapped[str | None] = mapped_column(String(256))
    legacy_non_executable: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    superseded_by_request_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("approval_requests.id")
    )
    clarification_request_id: Mapped[str | None] = mapped_column(String(128))
    requested_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    assigned_to: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    proposed_action: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    risk_level: Mapped[str] = mapped_column(String(32), nullable=False)
    risk_rule_ref: Mapped[str | None] = mapped_column(String(32))
    risk_reason: Mapped[str | None] = mapped_column(String(500))
    decision: Mapped[str | None] = mapped_column(String(32))
    reason: Mapped[str | None] = mapped_column(Text)
    decided_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resume_attempt_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    resume_attempt_decision_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "approval_decisions.id",
            name="fk_approval_requests_resume_attempt_decision",
            use_alter=True,
        ),
    )
    resume_attempt_status: Mapped[str | None] = mapped_column(String(32))
    resume_lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resume_attempt_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resume_attempt_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    thread_id: Mapped[str] = mapped_column(String(128), nullable=False)
    # thread_id is persisted so resume can reconstruct checkpoint_thread_id later.

    run: Mapped["AgentRun"] = relationship()
    steps: Mapped[list["ApprovalStep"]] = relationship(back_populates="approval_request", cascade="all, delete-orphan")
    levels: Mapped[list["ApprovalLevel"]] = relationship(
        back_populates="approval_request", cascade="all, delete-orphan"
    )
    decisions: Mapped[list["ApprovalDecision"]] = relationship(
        back_populates="approval_request",
        cascade="all, delete-orphan",
        foreign_keys="ApprovalDecision.approval_request_id",
    )
    events: Mapped[list["ApprovalEvent"]] = relationship(
        back_populates="approval_request", cascade="all, delete-orphan"
    )


Index("ix_approval_requests_tenant_status", ApprovalRequest.tenant_id, ApprovalRequest.status)
Index("ix_approval_requests_tenant_action_hash", ApprovalRequest.tenant_id, ApprovalRequest.action_payload_hash)
Index("ix_approval_requests_tenant_target_merchant", ApprovalRequest.tenant_id, ApprovalRequest.target_merchant_id)
Index(
    "ix_approval_requests_resume_attempt",
    ApprovalRequest.resume_attempt_status,
    ApprovalRequest.resume_lease_expires_at,
)
Index(
    "uq_approval_requests_active_revision",
    ApprovalRequest.tenant_id,
    ApprovalRequest.run_id,
    unique=True,
    postgresql_where=text("legacy_non_executable IS FALSE AND status IN ('pending', 'needs_info')"),
)


class ApprovalLevel(TimestampMixin, Base):
    __tablename__ = "approval_levels"
    __table_args__ = (
        UniqueConstraint("approval_request_id", "level_number", name="uq_approval_levels_request_level"),
        CheckConstraint(
            "status IN ('pending', 'approved', 'rejected', 'cancelled', 'expired', 'skipped')",
            name="ck_approval_levels_status",
        ),
        CheckConstraint("mode IN ('any_one', 'all')", name="ck_approval_levels_mode"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    approval_request_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("approval_requests.id"), nullable=False, index=True
    )
    schema_version: Mapped[str] = mapped_column(String(48), nullable=False, default="approval_level.v2")
    level_number: Mapped[int] = mapped_column(nullable=False)
    version: Mapped[int] = mapped_column(default=1, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    required_role: Mapped[str] = mapped_column(String(64), nullable=False)
    mode: Mapped[str] = mapped_column(String(32), nullable=False, default="any_one")
    sla_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    escalated_to_level: Mapped[int | None] = mapped_column()
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retention_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    approval_request: Mapped["ApprovalRequest"] = relationship(back_populates="levels")
    assignments: Mapped[list["ApprovalAssignment"]] = relationship(
        back_populates="approval_level", cascade="all, delete-orphan"
    )
    decisions: Mapped[list["ApprovalDecision"]] = relationship(
        back_populates="approval_level", cascade="all, delete-orphan"
    )


Index("ix_approval_levels_request", ApprovalLevel.approval_request_id)
Index("ix_approval_levels_status", ApprovalLevel.status)


class ApprovalAssignment(TimestampMixin, Base):
    __tablename__ = "approval_assignments"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'approved', 'rejected', 'cancelled', 'expired', 'skipped')",
            name="ck_approval_assignments_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    approval_level_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("approval_levels.id"), nullable=False, index=True
    )
    schema_version: Mapped[str] = mapped_column(String(48), nullable=False, default="approval_assignment.v2")
    assigned_role: Mapped[str] = mapped_column(String(64), nullable=False)
    assigned_to_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    version: Mapped[int] = mapped_column(default=1, nullable=False)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retention_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    approval_level: Mapped["ApprovalLevel"] = relationship(back_populates="assignments")
    decisions: Mapped[list["ApprovalDecision"]] = relationship(
        back_populates="approval_assignment", cascade="all, delete-orphan"
    )


Index("ix_approval_assignments_level", ApprovalAssignment.approval_level_id)
Index("ix_approval_assignments_status", ApprovalAssignment.status)


class ApprovalDecision(Base):
    __tablename__ = "approval_decisions"
    __table_args__ = (
        CheckConstraint(
            "decision_type IN ('accept', 'approve', 'edit', 'reject', 'respond', 'ignore', 'expire')",
            name="ck_approval_decisions_type",
        ),
        CheckConstraint("level_mode IN ('any_one', 'all')", name="ck_approval_decisions_level_mode"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    approval_request_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("approval_requests.id"), nullable=False
    )
    approval_level_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("approval_levels.id"), nullable=False
    )
    approval_assignment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("approval_assignments.id"), nullable=False
    )
    schema_version: Mapped[str] = mapped_column(String(48), nullable=False, default="approval_decision.v2")
    version: Mapped[int] = mapped_column(default=1, nullable=False)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("agent_runs.id"), nullable=False)
    thread_id: Mapped[str] = mapped_column(String(128), nullable=False)
    request_revision: Mapped[int] = mapped_column(nullable=False)
    request_version: Mapped[int] = mapped_column(nullable=False)
    level_version: Mapped[int] = mapped_column(nullable=False)
    level_mode: Mapped[str] = mapped_column(String(32), nullable=False)
    assignment_version: Mapped[int] = mapped_column(nullable=False)
    decision_type: Mapped[str] = mapped_column(String(32), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    response_text: Mapped[str | None] = mapped_column(Text)
    edited_action_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    actor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retention_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    approval_request: Mapped["ApprovalRequest"] = relationship(
        back_populates="decisions",
        foreign_keys=[approval_request_id],
    )
    approval_level: Mapped["ApprovalLevel"] = relationship(back_populates="decisions")
    approval_assignment: Mapped["ApprovalAssignment"] = relationship(back_populates="decisions")
    events: Mapped[list["ApprovalEvent"]] = relationship(back_populates="approval_decision")


Index("ix_approval_decisions_request", ApprovalDecision.approval_request_id)
Index("ix_approval_decisions_level", ApprovalDecision.approval_level_id)
Index("ix_approval_decisions_assignment", ApprovalDecision.approval_assignment_id)
Index("ix_approval_decisions_tenant_run", ApprovalDecision.tenant_id, ApprovalDecision.run_id)
Index(
    "uq_approval_decisions_active_assignment",
    ApprovalDecision.approval_assignment_id,
    unique=True,
    postgresql_where=text("deleted_at IS NULL AND archived_at IS NULL AND decision_type IN ('accept', 'approve')"),
)
Index(
    "uq_approval_decisions_winning_accept_level",
    ApprovalDecision.approval_level_id,
    unique=True,
    postgresql_where=text("deleted_at IS NULL AND level_mode = 'any_one' AND decision_type IN ('accept', 'approve')"),
)


class ApprovalEvent(Base):
    __tablename__ = "approval_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    approval_request_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("approval_requests.id"), nullable=False
    )
    approval_decision_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("approval_decisions.id")
    )
    replay_event_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_trace_events.event_id")
    )
    schema_version: Mapped[str] = mapped_column(String(48), nullable=False, default="approval_event.v2")
    version: Mapped[int] = mapped_column(default=1, nullable=False)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("agent_runs.id"), nullable=False)
    thread_id: Mapped[str] = mapped_column(String(128), nullable=False)
    request_revision: Mapped[int] = mapped_column(nullable=False)
    request_version: Mapped[int] = mapped_column(nullable=False)
    level_version: Mapped[int | None] = mapped_column()
    assignment_version: Mapped[int | None] = mapped_column()
    actor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    event_type: Mapped[str] = mapped_column(String(48), nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    resource_refs_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    redacted_payload_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retention_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    approval_request: Mapped["ApprovalRequest"] = relationship(back_populates="events")
    approval_decision: Mapped["ApprovalDecision | None"] = relationship(back_populates="events")


Index("ix_approval_events_request", ApprovalEvent.approval_request_id)
Index("ix_approval_events_decision", ApprovalEvent.approval_decision_id)
Index("ix_approval_events_replay_event", ApprovalEvent.replay_event_id)
Index("ix_approval_events_tenant_run", ApprovalEvent.tenant_id, ApprovalEvent.run_id)
Index("ix_approval_events_event_type", ApprovalEvent.event_type)


class ApprovalStep(Base):
    __tablename__ = "approval_steps"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    approval_request_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("approval_requests.id"), nullable=False, index=True
    )
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    # "created" | "approved" | "rejected" | "expired" | "resumed"
    actor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    approval_request: Mapped["ApprovalRequest"] = relationship(back_populates="steps")


class ActionDraft(TimestampMixin, Base):
    __tablename__ = "action_drafts"
    __table_args__ = (UniqueConstraint("tenant_id", "idempotency_key", name="uq_action_drafts_tenant_idempotency_key"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_runs.id"), nullable=False, index=True
    )
    approval_request_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("approval_requests.id")
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(256), nullable=False)
    schema_version: Mapped[str | None] = mapped_column(String(48), default="action_draft.v2")
    target_id: Mapped[str | None] = mapped_column(String(128))
    approval_revision_ref: Mapped[str | None] = mapped_column(String(256))
    action_payload_hash: Mapped[str | None] = mapped_column(String(128))
    safety_snapshot_ref: Mapped[str | None] = mapped_column(String(128))
    safety_snapshot_hash: Mapped[str | None] = mapped_column(String(128))
    target_merchant_id: Mapped[str | None] = mapped_column(String(128))
    target_merchant_ref: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    business_fact_refs: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB)
    verified_evidence_refs: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB)
    claim_verification_ref: Mapped[str | None] = mapped_column(String(128))
    claim_verification_summary: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    risk_decision_ref: Mapped[str | None] = mapped_column(String(128))
    risk_decision: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    auto_allowed_binding_ref: Mapped[str | None] = mapped_column(String(256))
    action_type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft_created")
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    draft_outcome: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    execution_mode: Mapped[str | None] = mapped_column(String(32), default="demo")
    draft_version: Mapped[int | None] = mapped_column(default=1)
    lifecycle_status: Mapped[str | None] = mapped_column(String(32), default="active")
    retention_policy: Mapped[str | None] = mapped_column(String(64), default="phase14_demo_draft")
    created_by_agent_run: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))


Index("ix_action_drafts_tenant_target_merchant", ActionDraft.tenant_id, ActionDraft.target_merchant_id)


class AutoActionCapability(Base):
    """Opaque, one-use authority for the sole durable demo draft handler."""

    __tablename__ = "auto_action_capabilities"
    __table_args__ = (
        UniqueConstraint("opaque_ref", name="uq_auto_action_capabilities_opaque_ref"),
        UniqueConstraint("nonce", name="uq_auto_action_capabilities_nonce"),
        CheckConstraint(
            "status IN ('issued', 'consumed', 'expired', 'revoked')",
            name="ck_auto_action_capabilities_status",
        ),
        CheckConstraint("expires_at > issued_at", name="ck_auto_action_capabilities_expiry"),
        CheckConstraint(
            "handler = 'create_coupon_grant_draft'",
            name="ck_auto_action_capabilities_handler",
        ),
        CheckConstraint("risk_disposition = 'allow'", name="ck_auto_action_capabilities_risk_disposition"),
        CheckConstraint(
            "((status = 'consumed' AND consumed_at IS NOT NULL "
            "AND resulting_draft_id IS NOT NULL AND idempotency_key IS NOT NULL) "
            "OR (status <> 'consumed' AND consumed_at IS NULL "
            "AND resulting_draft_id IS NULL AND idempotency_key IS NULL))",
            name="ck_auto_action_capabilities_consumption_state",
        ),
        ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_auto_action_capabilities_tenant",
        ),
        ForeignKeyConstraint(
            ["actor_id"],
            ["users.id"],
            name="fk_auto_action_capabilities_actor",
        ),
        ForeignKeyConstraint(
            ["run_id"],
            ["agent_runs.id"],
            name="fk_auto_action_capabilities_run",
        ),
        ForeignKeyConstraint(
            ["resulting_draft_id"],
            ["action_drafts.id"],
            name="fk_auto_action_capabilities_draft",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    schema_version: Mapped[str] = mapped_column(
        String(48),
        nullable=False,
        default="auto_action_capability.v1",
        server_default="auto_action_capability.v1",
    )
    key_version: Mapped[str] = mapped_column(
        String(48),
        nullable=False,
        default="opaque_ref_sha256.v1",
        server_default="opaque_ref_sha256.v1",
    )
    opaque_ref: Mapped[str] = mapped_column(String(96), nullable=False)
    nonce: Mapped[str] = mapped_column(String(64), nullable=False)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    actor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    merchant_scope_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    target_merchant_id: Mapped[str] = mapped_column(String(128), nullable=False)
    canonical_action: Mapped[str] = mapped_column(String(64), nullable=False)
    action_payload_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    safety_snapshot_ref: Mapped[str] = mapped_column(String(128), nullable=False)
    safety_snapshot_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    risk_decision_ref: Mapped[str] = mapped_column(String(128), nullable=False)
    risk_decision_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    risk_disposition: Mapped[str] = mapped_column(String(32), nullable=False)
    handler: Mapped[str] = mapped_column(String(64), nullable=False)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="issued", server_default="issued")
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resulting_draft_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    idempotency_key: Mapped[str | None] = mapped_column(String(256))


Index("ix_auto_action_capabilities_tenant_run", AutoActionCapability.tenant_id, AutoActionCapability.run_id)
Index(
    "ix_auto_action_capabilities_status_expiry",
    AutoActionCapability.status,
    AutoActionCapability.expires_at,
)


class AgentStep(TimestampMixin, Base):
    """One row per graph node traversal. Records node-level trace. Per D-05c."""

    __tablename__ = "agent_steps"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_runs.id"), nullable=False, index=True
    )
    node_name: Mapped[str] = mapped_column(String(64), nullable=False)
    step_index: Mapped[int] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    # "completed" | "error" | "skipped"
    input_summary: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    output_summary: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    tool_name: Mapped[str | None] = mapped_column(String(64))
    tool_input_summary: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    tool_output_summary: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    model_name: Mapped[str | None] = mapped_column(String(64))
    prompt_tokens: Mapped[int | None] = mapped_column()
    completion_tokens: Mapped[int | None] = mapped_column()
    latency_ms: Mapped[int | None] = mapped_column()
    provider_latency_ms: Mapped[int | None] = mapped_column()
    retry_count: Mapped[int | None] = mapped_column(default=0)
    metrics_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    evidence_refs: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB)
    # list of {"doc_key": str, "chunk_id": str}
    error_message: Mapped[str | None] = mapped_column(String(500))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    run: Mapped["AgentRun"] = relationship(back_populates="steps")


class ConversationThread(TimestampMixin, Base):
    __tablename__ = "conversation_threads"
    __table_args__ = (
        CheckConstraint("status IN ('active', 'archived')", name="ck_conversation_threads_status"),
        UniqueConstraint("id", "tenant_id", name="uq_conversation_threads_id_tenant"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    thread_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    case_id: Mapped[str | None] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retention_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    messages: Mapped[list["ConversationMessage"]] = relationship(back_populates="thread")
    tool_calls: Mapped[list["ToolCallRecord"]] = relationship(back_populates="thread")
    tool_results: Mapped[list["ToolResultRecord"]] = relationship(back_populates="thread")
    summaries: Mapped[list["ConversationSummary"]] = relationship(back_populates="thread")


Index(
    "uq_conversation_threads_active_tenant_user_thread",
    ConversationThread.tenant_id,
    ConversationThread.user_id,
    ConversationThread.thread_id,
    unique=True,
    postgresql_where=ConversationThread.deleted_at.is_(None),
)
Index(
    "ix_conversation_threads_tenant_user_thread",
    ConversationThread.tenant_id,
    ConversationThread.user_id,
    ConversationThread.thread_id,
)
Index("ix_conversation_threads_case_id", ConversationThread.case_id)


class ThreadCaseLink(TimestampMixin, Base):
    __tablename__ = "thread_case_links"
    __table_args__ = (
        CheckConstraint(
            "link_source IN ('run_auto', 'staff_manual', 'import')",
            name="ck_thread_case_links_link_source",
        ),
        ForeignKeyConstraint(
            ["conversation_thread_id", "tenant_id"],
            ["conversation_threads.id", "conversation_threads.tenant_id"],
            name="fk_thread_case_links_thread_tenant",
        ),
        ForeignKeyConstraint(
            ["case_id", "tenant_id"],
            ["refund_cases.id", "refund_cases.tenant_id"],
            name="fk_thread_case_links_case_tenant",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    conversation_thread_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversation_threads.id"), nullable=False
    )
    thread_id: Mapped[str] = mapped_column(String(128), nullable=False)
    case_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("refund_cases.id"), nullable=False)
    link_source: Mapped[str] = mapped_column(String(32), nullable=False)
    linked_by_run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("agent_runs.id"))
    schema_version: Mapped[str] = mapped_column(
        String(48), nullable=False, default="thread_case_link.v1", server_default="thread_case_link.v1"
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


Index("ix_thread_case_links_tenant_id", ThreadCaseLink.tenant_id)
Index(
    "ix_thread_case_links_tenant_case",
    ThreadCaseLink.tenant_id,
    ThreadCaseLink.case_id,
    postgresql_where=ThreadCaseLink.deleted_at.is_(None),
)
Index(
    "uq_thread_case_links_active",
    ThreadCaseLink.tenant_id,
    ThreadCaseLink.conversation_thread_id,
    ThreadCaseLink.case_id,
    unique=True,
    postgresql_where=ThreadCaseLink.deleted_at.is_(None),
)


class ConversationMessage(TimestampMixin, Base):
    __tablename__ = "conversation_messages"
    __table_args__ = (
        UniqueConstraint("conversation_thread_id", "message_index", name="uq_conversation_messages_thread_index"),
        CheckConstraint("role IN ('user', 'assistant', 'tool')", name="ck_conversation_messages_role"),
        CheckConstraint("message_index > 0", name="ck_conversation_messages_index_positive"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_thread_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversation_threads.id"), nullable=False, index=True
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    thread_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_runs.id"), nullable=False, index=True
    )
    trace_id: Mapped[str | None] = mapped_column(String(128))
    message_index: Mapped[int] = mapped_column(nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    prompt_template_version: Mapped[str | None] = mapped_column(String(64))
    prompt_block_hashes_json: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    context_snapshot_ref: Mapped[str | None] = mapped_column(String(255))
    redacted_prompt_snapshot_ref: Mapped[str | None] = mapped_column(String(255))
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retention_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    thread: Mapped["ConversationThread"] = relationship(back_populates="messages")


Index(
    "ix_conversation_messages_tenant_thread_index",
    ConversationMessage.tenant_id,
    ConversationMessage.thread_id,
    ConversationMessage.message_index,
)
Index("ix_conversation_messages_tenant_run", ConversationMessage.tenant_id, ConversationMessage.run_id)
Index("ix_conversation_messages_trace_id", ConversationMessage.trace_id)
Index(
    "uq_conversation_messages_active_tenant_run_role",
    ConversationMessage.tenant_id,
    ConversationMessage.run_id,
    ConversationMessage.role,
    unique=True,
    postgresql_where=text("deleted_at IS NULL AND run_id IS NOT NULL AND role IN ('user', 'assistant')"),
)


class ToolCallRecord(TimestampMixin, Base):
    __tablename__ = "tool_calls"
    __table_args__ = (CheckConstraint("attempt IS NULL OR attempt > 0", name="ck_tool_calls_attempt_positive"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_thread_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversation_threads.id"), nullable=False, index=True
    )
    message_id: Mapped[str | None] = mapped_column(String(128))
    conversation_message_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversation_messages.id"), index=True
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    thread_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("agent_runs.id"), index=True)
    trace_id: Mapped[str | None] = mapped_column(String(128))
    tool_call_id: Mapped[str] = mapped_column(String(128), nullable=False)
    tool_name: Mapped[str] = mapped_column(String(128), nullable=False)
    caller_node: Mapped[str | None] = mapped_column(String(64))
    operation_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    attempt: Mapped[int | None] = mapped_column()
    argument_summary_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    argument_hash: Mapped[str | None] = mapped_column(String(80))
    redaction_policy_version: Mapped[str] = mapped_column(
        String(48), nullable=False, default="conversation_redaction.v1"
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="started")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    latency_ms: Mapped[int | None] = mapped_column()
    error_summary: Mapped[str | None] = mapped_column(String(500))
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retention_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    thread: Mapped["ConversationThread"] = relationship(back_populates="tool_calls")
    results: Mapped[list["ToolResultRecord"]] = relationship(back_populates="tool_call")


Index("ix_tool_calls_tenant_thread_run", ToolCallRecord.tenant_id, ToolCallRecord.thread_id, ToolCallRecord.run_id)
Index("ix_tool_calls_tenant_operation", ToolCallRecord.tenant_id, ToolCallRecord.operation_id)
Index("ix_tool_calls_tool_call_id", ToolCallRecord.tool_call_id)


class ToolResultRecord(TimestampMixin, Base):
    __tablename__ = "tool_results"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_thread_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversation_threads.id"), nullable=False, index=True
    )
    tool_call_record_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("tool_calls.id"))
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    thread_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("agent_runs.id"), index=True)
    trace_id: Mapped[str | None] = mapped_column(String(128))
    operation_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    conversation_message_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversation_messages.id"), index=True
    )
    tool_call_id: Mapped[str | None] = mapped_column(String(128))
    tool_result_id: Mapped[str | None] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="success")
    source_system: Mapped[str | None] = mapped_column(String(128))
    data_freshness_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    latency_ms: Mapped[int | None] = mapped_column()
    raw_result_ref: Mapped[str | None] = mapped_column(String(255))
    raw_result_hash: Mapped[str | None] = mapped_column(String(80))
    normalized_result_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    prompt_summary: Mapped[str | None] = mapped_column(Text)
    business_fact_refs_json: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    policy_evidence_refs_json: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    audit_ref: Mapped[str | None] = mapped_column(String(255))
    replay_event_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retention_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    thread: Mapped["ConversationThread"] = relationship(back_populates="tool_results")
    tool_call: Mapped["ToolCallRecord | None"] = relationship(back_populates="results")


Index(
    "ix_tool_results_tenant_thread_run", ToolResultRecord.tenant_id, ToolResultRecord.thread_id, ToolResultRecord.run_id
)
Index("ix_tool_results_tenant_operation", ToolResultRecord.tenant_id, ToolResultRecord.operation_id)
Index("ix_tool_results_tool_result_id", ToolResultRecord.tool_result_id)
Index("ix_tool_results_replay_event_id", ToolResultRecord.replay_event_id)


class ConversationSummary(TimestampMixin, Base):
    __tablename__ = "summaries"
    __table_args__ = (CheckConstraint("summary_type IN ('thread_rolling', 'case_current')", name="ck_summaries_type"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    thread_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    conversation_thread_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversation_threads.id"), nullable=False, index=True
    )
    case_id: Mapped[str | None] = mapped_column(String(128))
    summary_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source_start_message_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    source_end_message_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    source_message_ids_json: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    source_tool_result_ids_json: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    summary_text: Mapped[str | None] = mapped_column(Text)
    summary_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    summary_model: Mapped[str | None] = mapped_column(String(128))
    summary_prompt_version: Mapped[str | None] = mapped_column(String(64))
    summary_hash: Mapped[str | None] = mapped_column(String(80))
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retention_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    thread: Mapped["ConversationThread"] = relationship(back_populates="summaries")


Index(
    "ix_summaries_tenant_thread_type",
    ConversationSummary.tenant_id,
    ConversationSummary.thread_id,
    ConversationSummary.summary_type,
)
Index("ix_summaries_case_id", ConversationSummary.case_id)
Index(
    "uq_summaries_thread_rolling_source_end",
    ConversationSummary.tenant_id,
    ConversationSummary.conversation_thread_id,
    ConversationSummary.summary_type,
    ConversationSummary.source_end_message_id,
    unique=True,
    postgresql_where=text(
        "deleted_at IS NULL AND summary_type = 'thread_rolling' AND source_end_message_id IS NOT NULL"
    ),
)


class AgentTraceEvent(TimestampMixin, Base):
    """Phase 10 minimal envelope expanded for Phase 15 ReplayEventV3 storage."""

    __tablename__ = "agent_trace_events"
    __table_args__ = (
        UniqueConstraint("run_id", "sequence", name="uq_agent_trace_events_run_seq"),
        UniqueConstraint("event_id", "tenant_id", name="uq_agent_trace_events_event_tenant"),
        CheckConstraint(
            "schema_version IN ('minimal_event_envelope.v1', 'replay_event.v3')",
            name="ck_agent_trace_events_schema_version",
        ),
        CheckConstraint(
            "event_type IN ("
            "'action_draft_created', 'approval_decided', 'approval_expired', 'approval_requested', "
            "'approval_resumed', 'llm_call_completed', 'llm_call_failed', 'llm_call_started', "
            "'memory_write_completed', 'memory_write_failed', 'memory_write_started', 'node_completed', "
            "'node_failed', 'node_started', 'rag_retrieval_completed', 'rag_retrieval_failed', "
            "'rag_retrieval_started', 'run_status_changed', 'tool_call_completed', 'tool_call_failed', "
            "'tool_call_started', 'tool_policy_runtime_auth_recorded', 'tool_policy_visibility_recorded')",
            name="ck_agent_trace_events_event_type",
        ),
        CheckConstraint("sequence > 0", name="ck_agent_trace_events_sequence_positive"),
        CheckConstraint("attempt IS NULL OR attempt > 0", name="ck_agent_trace_events_attempt_positive"),
    )

    event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_runs.id"), nullable=False, index=True
    )
    sequence: Mapped[int] = mapped_column(nullable=False)
    operation_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    parent_operation_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    attempt: Mapped[int | None] = mapped_column()
    version: Mapped[int | None] = mapped_column(default=1)
    node_name: Mapped[str | None] = mapped_column(String(64))
    approval_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("approval_requests.id"))
    draft_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("action_drafts.id"))
    tool_call_id: Mapped[str | None] = mapped_column(String(128))
    evidence_refs_json: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB)
    evidence_snapshot_refs_json: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB)
    error_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    thread_id: Mapped[str] = mapped_column(String(128), nullable=False)
    trace_id: Mapped[str | None] = mapped_column(String(128))
    event_type: Mapped[str] = mapped_column(String(48), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(48), nullable=False, default="minimal_event_envelope.v1")
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    actor: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    resource_refs: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    redaction_policy_version: Mapped[str] = mapped_column(String(48), nullable=False)
    redacted_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retention_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    run: Mapped["AgentRun"] = relationship(back_populates="trace_events")


Index(
    "ix_agent_trace_events_tenant_run_sequence",
    AgentTraceEvent.tenant_id,
    AgentTraceEvent.run_id,
    AgentTraceEvent.sequence,
)
Index(
    "ix_agent_trace_events_tenant_run_operation",
    AgentTraceEvent.tenant_id,
    AgentTraceEvent.run_id,
    AgentTraceEvent.operation_id,
)
Index("ix_agent_trace_events_tenant_occurred_at", AgentTraceEvent.tenant_id, AgentTraceEvent.occurred_at)
Index("ix_agent_trace_events_event_type_occurred_at", AgentTraceEvent.event_type, AgentTraceEvent.occurred_at)
