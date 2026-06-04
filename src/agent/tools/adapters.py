from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from src.agent.tools.contracts import ToolInvocationContext
from src.agent.tools.get_order import get_order
from src.agent.tools.get_refund_case import get_refund_case
from src.agent.tools.get_ticket import get_ticket
from src.agent.tools.search_policy import search_policy


class GetOrderInput(BaseModel):
    order_no: str = Field(min_length=1)


class GetRefundCaseInput(BaseModel):
    refund_case_no: str = Field(min_length=1)


class GetTicketInput(BaseModel):
    ticket_id: str = Field(min_length=1)


class SearchPolicyInput(BaseModel):
    query: str = Field(min_length=1)
    top_k: int = Field(default=5, ge=1, le=10)
    doc_type: str | None = None
    risk_level: str | None = None


async def get_order_adapter(input_data: BaseModel, context: ToolInvocationContext) -> dict[str, Any]:
    data = GetOrderInput.model_validate(input_data)
    return await get_order(data.order_no, context.tenant_id, context.user_id, context.role, context.session)


async def get_refund_case_adapter(input_data: BaseModel, context: ToolInvocationContext) -> dict[str, Any]:
    data = GetRefundCaseInput.model_validate(input_data)
    return await get_refund_case(
        data.refund_case_no,
        context.tenant_id,
        context.user_id,
        context.role,
        context.session,
    )


async def get_ticket_adapter(input_data: BaseModel, context: ToolInvocationContext) -> dict[str, Any]:
    data = GetTicketInput.model_validate(input_data)
    return await get_ticket(data.ticket_id, context.tenant_id, context.user_id, context.role, context.session)


async def search_policy_adapter(input_data: BaseModel, context: ToolInvocationContext) -> dict[str, Any]:
    data = SearchPolicyInput.model_validate(input_data)
    return await search_policy(
        data.query,
        context.tenant_id,
        context.user_id,
        context.role,
        context.session,
        top_k=data.top_k,
        doc_type=data.doc_type,
        risk_level=data.risk_level,
    )
