from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from typing import TYPE_CHECKING, Any
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from src.memory.case_identity import CaseIdentityResult, resolve_case_id
from src.memory.case_working_context import CaseWorkingContextRepository, hydrate_content
from src.memory.context_refs import CaseWorkingContextLifecycleStatusV1, CaseWorkingContextRef

if TYPE_CHECKING:
    from src.db.models import CaseWorkingContext


CaseResolver = Callable[..., Awaitable[CaseIdentityResult]]


class CaseWorkingContextLifecycleAdapter:
    def __init__(
        self,
        *,
        case_resolver: CaseResolver = resolve_case_id,
        repository_cls: type[CaseWorkingContextRepository] = CaseWorkingContextRepository,
    ) -> None:
        self._case_resolver = case_resolver
        self._repository_cls = repository_cls

    async def resolve_case(
        self,
        session: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        raw_case_ref: str | None,
    ) -> CaseIdentityResult:
        return await self._case_resolver(session, tenant_id=tenant_id, raw_case_ref=raw_case_ref)

    async def read_active_payload(
        self,
        session: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        case_id: uuid.UUID,
    ) -> dict[str, Any] | None:
        row = await self._repository_cls(session).read_active(tenant_id=tenant_id, case_id=case_id)
        if row is None:
            return None
        return build_active_cwc_payload(row)

    @staticmethod
    def trusted_case_ref_from_state(
        state: Mapping[str, Any],
        *,
        include_business_context: bool = False,
    ) -> str | None:
        return trusted_case_ref_from_state(state, include_business_context=include_business_context)

    @staticmethod
    def build_active_cwc_payload(row: CaseWorkingContext) -> dict[str, Any]:
        return build_active_cwc_payload(row)

    @staticmethod
    def skipped_status(reason_code: str, **overrides: Any) -> CaseWorkingContextLifecycleStatusV1:
        return skipped_status(reason_code=reason_code, **overrides)


def trusted_case_ref_from_state(
    state: Mapping[str, Any],
    *,
    include_business_context: bool = False,
) -> str | None:
    active_slots_ref = _mapping_value(state.get("active_slots"), "refund_case_id")
    if active_slots_ref is not None:
        return active_slots_ref

    extracted_slots_ref = _mapping_value(state.get("extracted_slots"), "refund_case_id")
    if extracted_slots_ref is not None:
        return extracted_slots_ref

    if not include_business_context:
        return None

    refund_case = _mapping_value(state.get("business_context"), "refund_case")
    if not isinstance(refund_case, Mapping):
        return None

    for key in ("refund_case_no", "refund_case_id", "id"):
        value = _non_empty_str(refund_case.get(key))
        if value is not None:
            return value
    return None


def build_active_cwc_payload(row: CaseWorkingContext) -> dict[str, Any]:
    content = hydrate_content(row).model_dump(mode="json")
    ref = CaseWorkingContextRef(
        tenant_id=str(row.tenant_id),
        case_id=str(row.case_id),
        memory_id=str(row.id),
        version=row.version,
        source_ref=dict(row.source_ref_json or {}),
        updated_by_run_id=str(row.updated_by_run_id) if row.updated_by_run_id is not None else None,
    )
    return {
        "content": content,
        "ref": ref.model_dump(mode="json"),
    }


def skipped_status(reason_code: str, **overrides: Any) -> CaseWorkingContextLifecycleStatusV1:
    return lifecycle_status(status="skipped", reason_code=reason_code, **overrides)


def error_status(reason_code: str, **overrides: Any) -> CaseWorkingContextLifecycleStatusV1:
    return lifecycle_status(status="error", reason_code=reason_code, **overrides)


def lifecycle_status(
    *,
    status: str,
    resolve_status: str | None = None,
    link_status: str | None = None,
    read_status: str | None = None,
    write_status: str | None = None,
    reason_code: str | None = None,
    filter_reasons: list[str] | None = None,
    tenant_id: uuid.UUID | str | None = None,
    case_id: uuid.UUID | str | None = None,
    run_id: uuid.UUID | str | None = None,
    raw_case_ref: str | None = None,
) -> CaseWorkingContextLifecycleStatusV1:
    return CaseWorkingContextLifecycleStatusV1(
        status=status,
        resolve_status=resolve_status,
        link_status=link_status,
        read_status=read_status,
        write_status=write_status,
        reason_code=reason_code,
        filter_reasons=list(filter_reasons or []),
        tenant_id=str(tenant_id) if tenant_id is not None else None,
        case_id=str(case_id) if case_id is not None else None,
        run_id=str(run_id) if run_id is not None else None,
        raw_case_ref=raw_case_ref,
    )


def _mapping_value(container: Any, key: str) -> Any:
    if not isinstance(container, Mapping):
        return None
    return container.get(key)


def _non_empty_str(value: Any) -> str | None:
    if value is None:
        return None
    stripped = str(value).strip()
    return stripped or None
