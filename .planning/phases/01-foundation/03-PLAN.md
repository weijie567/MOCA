---
phase: 1
plan_id: "03"
title: "Repository Layer + Read API Endpoints"
wave: 2
depends_on: ["01", "02"]
files_modified:
  - src/repositories/__init__.py
  - src/repositories/base.py
  - src/repositories/order_repo.py
  - src/repositories/refund_repo.py
  - src/repositories/ticket_repo.py
  - src/repositories/audit_repo.py
  - src/api/routers/orders.py
  - src/api/routers/refund_cases.py
  - src/api/routers/tickets.py
  - src/api/schemas/orders.py
  - src/api/schemas/refund_cases.py
  - src/api/schemas/tickets.py
autonomous: true
requirements: [TOOL-01, TOOL-02, TOOL-03, TOOL-06, TOOL-07, INFR-04, INFR-05]
---

# Plan 03: Repository Layer + Read API Endpoints

<objective>
Implement the repository pattern with tenant-scoped queries, then build the three read tool API endpoints (get_order, get_refund_case, get_ticket_history) with proper input/output schemas, audit logging, and relation_hints on orders.
</objective>

<tasks>

<task id="03-01">
<title>Create base repository with tenant scoping</title>
<read_first>
- src/db/models.py
- src/db/session.py
</read_first>
<action>
Create `src/repositories/__init__.py` (empty).
Create `src/repositories/base.py`:

```python
from typing import Generic, TypeVar, Type
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

T = TypeVar("T")

class BaseRepository(Generic[T]):
    model: Type[T]

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, id: UUID, tenant_id: UUID) -> T | None:
        stmt = select(self.model).where(
            self.model.id == id,
            self.model.tenant_id == tenant_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_all(
        self, tenant_id: UUID, limit: int = 50, offset: int = 0, **filters
    ) -> list[T]:
        stmt = select(self.model).where(self.model.tenant_id == tenant_id)
        for key, value in filters.items():
            if value is not None and hasattr(self.model, key):
                stmt = stmt.where(getattr(self.model, key) == value)
        stmt = stmt.order_by(self.model.created_at.desc()).limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
```

Key: every query method requires tenant_id. No method exposes cross-tenant data.
</action>
<acceptance_criteria>
- src/repositories/base.py contains `class BaseRepository(Generic[T])`
- src/repositories/base.py contains `tenant_id` in get_by_id signature
- src/repositories/base.py contains `self.model.tenant_id == tenant_id`
- src/repositories/base.py contains `async def list_all`
- src/repositories/base.py contains `limit: int = 50`
</acceptance_criteria>
</task>

<task id="03-02">
<title>Create order repository with relation_hints</title>
<read_first>
- src/repositories/base.py
- src/db/models.py
- .planning/phases/01-foundation/01-CONTEXT.md (D-11: relation_hints)
</read_first>
<action>
Create `src/repositories/order_repo.py`:

```python
class OrderRepository(BaseRepository[Order]):
    model = Order

    async def get_with_hints(self, order_id: UUID, tenant_id: UUID) -> dict | None:
        order = await self.get_by_id(order_id, tenant_id)
        if not order:
            return None

        # Check for active refund
        refund_stmt = select(RefundCase).where(
            RefundCase.order_id == order_id,
            RefundCase.tenant_id == tenant_id,
            RefundCase.status.not_in(["refunded", "rejected", "closed"]),
        ).order_by(RefundCase.created_at.desc()).limit(1)
        refund_result = await self.session.execute(refund_stmt)
        active_refund = refund_result.scalar_one_or_none()

        # Check for open ticket
        ticket_stmt = select(Ticket).where(
            Ticket.order_id == order_id,
            Ticket.tenant_id == tenant_id,
            Ticket.status.in_(["open", "in_progress"]),
        ).order_by(Ticket.created_at.desc()).limit(1)
        ticket_result = await self.session.execute(ticket_stmt)
        open_ticket = ticket_result.scalar_one_or_none()

        return {
            "order": order,
            "relation_hints": {
                "has_active_refund": active_refund is not None,
                "latest_refund_case_id": str(active_refund.id) if active_refund else None,
                "has_open_ticket": open_ticket is not None,
                "latest_ticket_id": str(open_ticket.id) if open_ticket else None,
            }
        }

    async def list_for_merchant(self, tenant_id: UUID, merchant_id: UUID, limit: int = 50, offset: int = 0) -> list[Order]:
        stmt = select(Order).where(
            Order.tenant_id == tenant_id,
            Order.merchant_id == merchant_id,
        ).limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
```
</action>
<acceptance_criteria>
- src/repositories/order_repo.py contains `class OrderRepository(BaseRepository`
- src/repositories/order_repo.py contains `get_with_hints`
- src/repositories/order_repo.py contains `has_active_refund`
- src/repositories/order_repo.py contains `latest_refund_case_id`
- src/repositories/order_repo.py contains `has_open_ticket`
- src/repositories/order_repo.py contains `latest_ticket_id`
- src/repositories/order_repo.py contains `list_for_merchant`
</acceptance_criteria>
</task>

<task id="03-03">
<title>Create refund and ticket repositories</title>
<read_first>
- src/repositories/base.py
- src/db/models.py
</read_first>
<action>
Create `src/repositories/refund_repo.py`:
```python
class RefundCaseRepository(BaseRepository[RefundCase]):
    model = RefundCase

    async def list_for_merchant(self, tenant_id: UUID, merchant_id: UUID, limit: int = 50, offset: int = 0) -> list[RefundCase]:
        # JOIN orders to filter by merchant_id
        stmt = (
            select(RefundCase)
            .join(Order, RefundCase.order_id == Order.id)
            .where(RefundCase.tenant_id == tenant_id, Order.merchant_id == merchant_id)
            .limit(limit).offset(offset)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
```

Create `src/repositories/ticket_repo.py`:
```python
class TicketRepository(BaseRepository[Ticket]):
    model = Ticket

    async def list_for_merchant(self, tenant_id: UUID, merchant_id: UUID, limit: int = 50, offset: int = 0) -> list[Ticket]:
        stmt = (
            select(Ticket)
            .join(Order, Ticket.order_id == Order.id)
            .where(Ticket.tenant_id == tenant_id, Order.merchant_id == merchant_id)
            .limit(limit).offset(offset)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
```
</action>
<acceptance_criteria>
- src/repositories/refund_repo.py contains `class RefundCaseRepository(BaseRepository`
- src/repositories/refund_repo.py contains `list_for_merchant`
- src/repositories/ticket_repo.py contains `class TicketRepository(BaseRepository`
- src/repositories/ticket_repo.py contains `list_for_merchant`
- Both files contain `tenant_id` in query filters
</acceptance_criteria>
</task>

<task id="03-04">
<title>Create audit repository for logging tool calls</title>
<read_first>
- src/repositories/base.py
- src/db/models.py
- .planning/phases/01-foundation/01-CONTEXT.md (D-08: audit log fields)
</read_first>
<action>
Create `src/repositories/audit_repo.py`:

```python
class AuditRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def log(
        self,
        tenant_id: UUID,
        user_id: UUID | None,
        role: str | None,
        action: str,
        resource_type: str,
        resource_id: str | None,
        trace_id: str,
    ) -> AuditLog:
        entry = AuditLog(
            tenant_id=tenant_id,
            user_id=user_id,
            role=role,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            trace_id=trace_id,
        )
        self.session.add(entry)
        # Do NOT commit here — let the router/endpoint commit once at the end
        # This avoids coupling read-endpoint success to audit-write success
        await self.session.flush()
        return entry
```
</action>
<acceptance_criteria>
- src/repositories/audit_repo.py contains `class AuditRepository`
- src/repositories/audit_repo.py contains `async def log`
- src/repositories/audit_repo.py contains `tenant_id`
- src/repositories/audit_repo.py contains `trace_id`
- src/repositories/audit_repo.py contains `resource_type`
</acceptance_criteria>
</task>

<task id="03-05">
<title>Create API schemas for orders, refund_cases, tickets</title>
<read_first>
- .planning/phases/01-foundation/01-RESEARCH.md (Section 7: Tool Return Structure)
- src/db/models.py
</read_first>
<action>
Create `src/api/schemas/orders.py`:
- OrderResponse: id, order_no, merchant_name, product_name, amount(float), status, created_at, delivered_at(optional)
- RelationHints: has_active_refund(bool), latest_refund_case_id(str|None), has_open_ticket(bool), latest_ticket_id(str|None)
- OrderDetailResponse: OrderResponse + relation_hints(RelationHints)
- OrderListResponse: items(list[OrderResponse]), total(int)

Create `src/api/schemas/refund_cases.py`:
- RefundCaseResponse: id, refund_case_no, order_id, reason_code, reason_text, status, requested_amount(float), created_at
- RefundCaseListResponse: items(list[RefundCaseResponse]), total(int)

Create `src/api/schemas/tickets.py`:
- TicketResponse: id, order_id, refund_case_id(optional), channel, status, summary, created_at
- TicketListResponse: items(list[TicketResponse]), total(int)
</action>
<acceptance_criteria>
- src/api/schemas/orders.py contains `class OrderResponse`
- src/api/schemas/orders.py contains `class RelationHints`
- src/api/schemas/orders.py contains `has_active_refund`
- src/api/schemas/refund_cases.py contains `class RefundCaseResponse`
- src/api/schemas/refund_cases.py contains `reason_code`
- src/api/schemas/tickets.py contains `class TicketResponse`
- src/api/schemas/tickets.py contains `summary`
</acceptance_criteria>
</task>

<task id="03-06">
<title>Create orders router with audit logging</title>
<read_first>
- src/repositories/order_repo.py
- src/repositories/audit_repo.py
- src/api/schemas/orders.py
- src/auth/permissions.py
</read_first>
<action>
Create `src/api/routers/orders.py`:

GET /api/v1/orders/{order_id}:
  - Depends: require_roles(["support", "manager", "merchant", "admin"])
  - If merchant role: verify order belongs to user's merchant_id, else 404
  - Call OrderRepository.get_with_hints(order_id, user.tenant_id)
  - Log to audit: action="get_order", resource_type="order", resource_id=order_id
  - Return ApiResponse(success=True, data=OrderDetailResponse, trace_id=...)
  - 404 if not found: ApiResponse(success=False, error=ErrorDetail(code="ORDER_NOT_FOUND"))

GET /api/v1/orders/:
  - Depends: require_roles(["support", "manager", "admin"]) OR merchant (own only)
  - Pagination: limit, offset query params
  - If merchant: use list_for_merchant
  - Else: use list_all with tenant_id
  - Return ApiResponse(success=True, data=OrderListResponse)
</action>
<acceptance_criteria>
- src/api/routers/orders.py contains `@router.get("/{order_id}")`
- src/api/routers/orders.py contains `require_roles`
- src/api/routers/orders.py contains `OrderRepository`
- src/api/routers/orders.py contains `audit` or `AuditRepository`
- src/api/routers/orders.py contains `ORDER_NOT_FOUND`
- src/api/routers/orders.py contains `trace_id`
</acceptance_criteria>
</task>

<task id="03-07">
<title>Create refund_cases and tickets routers</title>
<read_first>
- src/api/routers/orders.py (pattern to follow)
- src/repositories/refund_repo.py
- src/repositories/ticket_repo.py
- src/api/schemas/refund_cases.py
- src/api/schemas/tickets.py
</read_first>
<action>
Create `src/api/routers/refund_cases.py`:
- GET /api/v1/refund-cases/{refund_case_id}: same pattern as orders (tenant scope, merchant check, audit log)
- GET /api/v1/refund-cases/: list with pagination, merchant filtering
- Error code: REFUND_CASE_NOT_FOUND

Create `src/api/routers/tickets.py`:
- GET /api/v1/tickets/{ticket_id}: same pattern
- GET /api/v1/tickets/: list with pagination, merchant filtering
- Error code: TICKET_NOT_FOUND

Both routers:
- Use require_roles(["support", "manager", "merchant", "admin"])
- Merchant role sees only own merchant's data
- All operations log to audit_logs
- All responses wrapped in ApiResponse with trace_id
</action>
<acceptance_criteria>
- src/api/routers/refund_cases.py contains `@router.get("/{refund_case_id}")`
- src/api/routers/refund_cases.py contains `REFUND_CASE_NOT_FOUND`
- src/api/routers/refund_cases.py contains `AuditRepository` or `audit`
- src/api/routers/tickets.py contains `@router.get("/{ticket_id}")`
- src/api/routers/tickets.py contains `TICKET_NOT_FOUND`
- src/api/routers/tickets.py contains `trace_id`
</acceptance_criteria>
</task>

<task id="03-08">
<title>Register all routers in main.py</title>
<read_first>
- src/api/main.py
- src/api/routers/orders.py
- src/api/routers/refund_cases.py
- src/api/routers/tickets.py
</read_first>
<action>
Update `src/api/main.py` to include:
- app.include_router(orders_router, prefix="/api/v1/orders", tags=["orders"])
- app.include_router(refund_cases_router, prefix="/api/v1/refund-cases", tags=["refund-cases"])
- app.include_router(tickets_router, prefix="/api/v1/tickets", tags=["tickets"])
</action>
<acceptance_criteria>
- src/api/main.py contains `"/api/v1/orders"`
- src/api/main.py contains `"/api/v1/refund-cases"`
- src/api/main.py contains `"/api/v1/tickets"`
</acceptance_criteria>
</task>

</tasks>

<verification>
- Swagger UI at /docs shows all endpoints with proper schemas
- GET /api/v1/orders/{id} with valid token returns order with relation_hints
- GET /api/v1/orders/{id} with wrong tenant returns 404 (not 403)
- GET /api/v1/refund-cases/{id} returns refund case data
- GET /api/v1/tickets/{id} returns ticket data
- Merchant role can only see own merchant's data
- All responses include trace_id
- audit_logs table has entries after API calls
</verification>

<must_haves>
- Repository layer enforces tenant_id on every query
- Merchant role restricted to own merchant's data
- get_order returns relation_hints (has_active_refund, latest_refund_case_id, has_open_ticket, latest_ticket_id)
- All tool calls logged to audit_logs with trace_id
- All responses follow unified format
- Input/output schemas clearly defined (TOOL-06)
</must_haves>

<threat_model>
| Threat | Severity | Mitigation |
|--------|----------|-----------|
| IDOR (accessing other tenant's data) | High | tenant_id filter in every repository query; 404 not 403 to prevent enumeration |
| Merchant accessing other merchant's data | High | merchant_id check in router before repo call |
| Missing audit trail | Medium | AuditRepository.log called in every endpoint |
| SQL injection via filter params | Low | SQLAlchemy parameterized queries only |
</threat_model>
