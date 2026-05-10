from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Numeric, String, Text, UniqueConstraint, func
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
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)
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
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)
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
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)
    merchant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("merchants.id"), nullable=False, index=True)
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
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)
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
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)
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
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)
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
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)
    doc_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("policy_documents.id"), nullable=False, index=True)
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
