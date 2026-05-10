import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class RelationHints(BaseModel):
    has_active_refund: bool
    latest_refund_case_id: uuid.UUID | None = None
    has_open_ticket: bool
    latest_ticket_id: uuid.UUID | None = None


class OrderResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    merchant_id: uuid.UUID
    order_no: str
    buyer_name: str
    item_name: str
    amount: Decimal
    currency: str
    status: str
    created_at: datetime
    delivered_at: datetime | None = None
    relation_hints: RelationHints
