import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class TicketHistoryResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    order_id: uuid.UUID
    refund_case_id: uuid.UUID | None = None
    ticket_no: str
    channel: str
    status: str
    summary: str
    created_at: datetime
    messages: list[dict[str, Any]]
