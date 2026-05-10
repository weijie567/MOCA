import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class RefundCaseResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    order_id: uuid.UUID
    refund_case_no: str
    reason_code: str
    reason_text: str
    status: str
    requested_amount: Decimal
    approved_amount: Decimal | None = None
    created_at: datetime
