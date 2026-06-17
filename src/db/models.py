from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, Index, Numeric, String, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
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
    users: Mapped[list["User"]] = relationship(back_populates="merchant")


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    merchant_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("merchants.id"))
    username: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    tenant: Mapped["Tenant"] = relationship(back_populates="users")
    merchant: Mapped["Merchant | None"] = relationship(back_populates="users")
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
    __table_args__ = (UniqueConstraint("tenant_id", "doc_key", name="uq_policy_documents_tenant_doc_key"),)

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

    chunks: Mapped[list["PolicyChunk"]] = relationship(back_populates="document")


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
    risk_level: Mapped[str] = mapped_column(String(32), nullable=False)
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1024))

    document: Mapped["PolicyDocument"] = relationship(back_populates="chunks")


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

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    thread_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    input_query: Mapped[str] = mapped_column(Text, nullable=False)
    final_status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    # "completed" | "error" | "insufficient_evidence"
    final_response: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    total_latency_ms: Mapped[int | None] = mapped_column()
    total_tokens: Mapped[int | None] = mapped_column()
    total_cost: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))
    error_summary: Mapped[str | None] = mapped_column(String(500))

    steps: Mapped[list["AgentStep"]] = relationship(back_populates="run", cascade="all, delete-orphan")
    trace_events: Mapped[list["AgentTraceEvent"]] = relationship(back_populates="run", cascade="all, delete-orphan")


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


class ActionSafetySnapshot(Base):
    __tablename__ = "action_safety_snapshots"
    __table_args__ = (
        UniqueConstraint("tenant_id", "immutable_hash", name="uq_action_safety_snapshots_tenant_hash"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    schema_version: Mapped[str] = mapped_column(String(48), nullable=False, default="action_safety_snapshot.v1")
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("agent_runs.id"), nullable=False)
    snapshot_ref: Mapped[str] = mapped_column(String(128), nullable=False)
    snapshot_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    immutable_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    action_payload_hash: Mapped[str | None] = mapped_column(String(128))
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


class ApprovalRequest(TimestampMixin, Base):
    __tablename__ = "approval_requests"
    __table_args__ = (
        UniqueConstraint("tenant_id", "run_id", "revision", name="uq_approval_requests_tenant_run_revision"),
        CheckConstraint(
            "status IN ('pending', 'needs_info', 'approved', 'rejected', 'cancelled', 'expired', 'superseded')",
            name="ck_approval_requests_status",
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
    postgresql_where=text(
        "deleted_at IS NULL AND level_mode = 'any_one' AND decision_type IN ('accept', 'approve')"
    ),
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
    __table_args__ = (
        UniqueConstraint("tenant_id", "idempotency_key", name="uq_action_drafts_tenant_idempotency_key"),
    )

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
    approval_revision_ref: Mapped[str | None] = mapped_column(String(128))
    action_payload_hash: Mapped[str | None] = mapped_column(String(128))
    safety_snapshot_ref: Mapped[str | None] = mapped_column(String(128))
    safety_snapshot_hash: Mapped[str | None] = mapped_column(String(128))
    action_type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft_created")
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    draft_outcome: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    execution_mode: Mapped[str | None] = mapped_column(String(32), default="demo")
    draft_version: Mapped[int | None] = mapped_column(default=1)
    lifecycle_status: Mapped[str | None] = mapped_column(String(32), default="active")
    retention_policy: Mapped[str | None] = mapped_column(String(64), default="phase14_demo_draft")
    created_by_agent_run: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))


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
    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("agent_runs.id"), nullable=False, index=True)
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


class ToolCallRecord(TimestampMixin, Base):
    __tablename__ = "tool_calls"
    __table_args__ = (
        CheckConstraint("attempt IS NULL OR attempt > 0", name="ck_tool_calls_attempt_positive"),
    )

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
    redaction_policy_version: Mapped[str] = mapped_column(String(48), nullable=False, default="conversation_redaction.v1")
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


Index("ix_tool_results_tenant_thread_run", ToolResultRecord.tenant_id, ToolResultRecord.thread_id, ToolResultRecord.run_id)
Index("ix_tool_results_tenant_operation", ToolResultRecord.tenant_id, ToolResultRecord.operation_id)
Index("ix_tool_results_tool_result_id", ToolResultRecord.tool_result_id)
Index("ix_tool_results_replay_event_id", ToolResultRecord.replay_event_id)


class ConversationSummary(TimestampMixin, Base):
    __tablename__ = "summaries"
    __table_args__ = (
        CheckConstraint("summary_type IN ('thread_rolling', 'case_current')", name="ck_summaries_type"),
    )

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


Index("ix_summaries_tenant_thread_type", ConversationSummary.tenant_id, ConversationSummary.thread_id, ConversationSummary.summary_type)
Index("ix_summaries_case_id", ConversationSummary.case_id)


class AgentTraceEvent(TimestampMixin, Base):
    """Phase 10 minimal envelope expanded for Phase 15 ReplayEventV3 storage."""

    __tablename__ = "agent_trace_events"
    __table_args__ = (
        UniqueConstraint("run_id", "sequence", name="uq_agent_trace_events_run_seq"),
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
            "'tool_call_started')",
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
    error_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    thread_id: Mapped[str] = mapped_column(String(128), nullable=False)
    trace_id: Mapped[str | None] = mapped_column(String(128))
    event_type: Mapped[str] = mapped_column(String(48), nullable=False)
    schema_version: Mapped[str] = mapped_column(
        String(48), nullable=False, default="minimal_event_envelope.v1"
    )
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    actor: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    resource_refs: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    redaction_policy_version: Mapped[str] = mapped_column(String(48), nullable=False)
    redacted_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retention_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    run: Mapped["AgentRun"] = relationship(back_populates="trace_events")


Index("ix_agent_trace_events_tenant_run_sequence", AgentTraceEvent.tenant_id, AgentTraceEvent.run_id, AgentTraceEvent.sequence)
Index(
    "ix_agent_trace_events_tenant_run_operation",
    AgentTraceEvent.tenant_id,
    AgentTraceEvent.run_id,
    AgentTraceEvent.operation_id,
)
Index("ix_agent_trace_events_tenant_occurred_at", AgentTraceEvent.tenant_id, AgentTraceEvent.occurred_at)
Index("ix_agent_trace_events_event_type_occurred_at", AgentTraceEvent.event_type, AgentTraceEvent.occurred_at)
