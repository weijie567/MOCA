from __future__ import annotations

from decimal import Decimal
import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import RefundCase
from src.memory.case_identity import resolve_case_id


@pytest.mark.asyncio
async def test_resolve_case_id_resolves_refund_case_no(
    session: AsyncSession,
    seeded_session: dict,
) -> None:
    refund_case = seeded_session["refund_case"]

    result = await resolve_case_id(
        session,
        tenant_id=seeded_session["tenant"].id,
        raw_case_ref=refund_case.refund_case_no,
    )

    assert result.status == "resolved"
    assert result.case_id == refund_case.id
    assert result.input_form == "refund_case_no"


@pytest.mark.asyncio
async def test_resolve_case_id_resolves_uuid_string(
    session: AsyncSession,
    seeded_session: dict,
) -> None:
    refund_case = seeded_session["refund_case"]

    result = await resolve_case_id(
        session,
        tenant_id=seeded_session["tenant"].id,
        raw_case_ref=str(refund_case.id),
    )

    assert result.status == "resolved"
    assert result.case_id == refund_case.id
    assert result.input_form == "uuid"


@pytest.mark.asyncio
async def test_resolve_case_id_unknown_case_no_returns_not_found(
    session: AsyncSession,
    seeded_session: dict,
) -> None:
    result = await resolve_case_id(
        session,
        tenant_id=seeded_session["tenant"].id,
        raw_case_ref="RF-DOES-NOT-EXIST",
    )

    assert result.status == "not_found"
    assert result.case_id is None
    assert result.input_form == "refund_case_no"


@pytest.mark.asyncio
async def test_resolve_case_id_unknown_uuid_returns_not_found_as_uuid(
    session: AsyncSession,
    seeded_session: dict,
) -> None:
    result = await resolve_case_id(
        session,
        tenant_id=seeded_session["tenant"].id,
        raw_case_ref=str(uuid.uuid4()),
    )

    assert result.status == "not_found"
    assert result.case_id is None
    assert result.input_form == "uuid"


@pytest.mark.asyncio
async def test_resolve_case_id_blank_input_is_invalid_without_query(
    seeded_session: dict,
) -> None:
    class NoQuerySession:
        async def execute(self, *args, **kwargs):  # pragma: no cover - failure path only
            raise AssertionError("blank case refs must not query the database")

    result = await resolve_case_id(
        NoQuerySession(),  # type: ignore[arg-type]
        tenant_id=seeded_session["tenant"].id,
        raw_case_ref="  ",
    )

    assert result.status == "invalid"
    assert result.case_id is None
    assert result.input_form == "unknown"


@pytest.mark.asyncio
async def test_resolve_case_id_none_input_is_invalid_without_query(
    seeded_session: dict,
) -> None:
    class NoQuerySession:
        async def execute(self, *args, **kwargs):  # pragma: no cover - failure path only
            raise AssertionError("missing case refs must not query the database")

    result = await resolve_case_id(
        NoQuerySession(),  # type: ignore[arg-type]
        tenant_id=seeded_session["tenant"].id,
        raw_case_ref=None,
    )

    assert result.status == "invalid"
    assert result.case_id is None
    assert result.input_form == "unknown"


@pytest.mark.asyncio
async def test_resolve_case_id_is_tenant_scoped(
    session: AsyncSession,
    seeded_session: dict,
) -> None:
    other_case_no = "RF-OTHER-TENANT-001"
    other_case = RefundCase(
        id=uuid.uuid4(),
        tenant_id=seeded_session["other_tenant"].id,
        order_id=seeded_session["other_order"].id,
        refund_case_no=other_case_no,
        reason_code="damaged",
        reason_text="其他租户退款单",
        status="reviewing",
        requested_amount=Decimal("399.00"),
    )
    session.add(other_case)
    await session.flush()

    result = await resolve_case_id(
        session,
        tenant_id=seeded_session["tenant"].id,
        raw_case_ref=other_case_no,
    )

    assert result.status == "not_found"
    assert result.case_id is None
    assert result.input_form == "refund_case_no"
