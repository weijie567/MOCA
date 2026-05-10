from typing import Any

from pydantic import BaseModel, Field


UNAUTHORIZED = "UNAUTHORIZED"
FORBIDDEN = "FORBIDDEN"
VALIDATION_ERROR = "VALIDATION_ERROR"
ORDER_NOT_FOUND = "ORDER_NOT_FOUND"
REFUND_CASE_NOT_FOUND = "REFUND_CASE_NOT_FOUND"
TICKET_NOT_FOUND = "TICKET_NOT_FOUND"
POLICY_DOCUMENT_NOT_FOUND = "POLICY_DOCUMENT_NOT_FOUND"
TENANT_SCOPE_VIOLATION = "TENANT_SCOPE_VIOLATION"
INTERNAL_ERROR = "INTERNAL_ERROR"


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class ApiResponse(BaseModel):
    success: bool
    data: Any | None = None
    error: ErrorDetail | None = None
    trace_id: str | None = None
