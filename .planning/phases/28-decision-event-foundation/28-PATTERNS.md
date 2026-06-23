# Phase 28: Decision Event Foundation - Pattern Map

**Mapped:** 2026-06-23
**Files analyzed:** 10 new/modified files
**Analogs found:** 10 / 10

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/replay/decision_events.py` | service / contract facade | event-driven + CRUD | `src/replay/schemas.py`, `src/replay/service.py`, `src/replay/validators.py`, `src/platform/context_projections.py` | exact composite |
| `src/replay/validators.py` | utility | transform / validation | `src/replay/validators.py`, `src/approvals/events.py` | exact |
| `src/replay/service.py` | service | event-driven + CRUD | `src/replay/service.py` | exact |
| `src/agent/events.py` | utility / compatibility wrapper | event-driven | `src/agent/events.py` | exact |
| `src/replay/__init__.py` | package export / config | transform | `src/replay/__init__.py` | exact |
| `tests/replay/test_decision_events.py` | test | event-driven + CRUD | `tests/replay/test_replay_service.py`, `tests/agent/test_events.py` | exact composite |
| `tests/agent/test_events.py` | test | event-driven | `tests/agent/test_events.py` | exact |
| `tests/replay/test_sequence_allocator.py` | test | event-driven + CRUD | `tests/replay/test_sequence_allocator.py` | exact |
| `tests/platform/test_context_projections.py` | test | transform | `tests/platform/test_context_projections.py` | exact |
| `tests/replay/test_replay_service.py` | test | event-driven + CRUD | `tests/replay/test_replay_service.py` | role-match |

## Pattern Assignments

### `src/replay/decision_events.py` (service / contract facade, event-driven + CRUD)

**Analogs:** `src/replay/schemas.py`, `src/replay/service.py`, `src/replay/validators.py`, `src/platform/context_projections.py`, `src/replay/pairing.py`

**Imports pattern** (`src/replay/schemas.py` lines 5-11, `src/replay/service.py` lines 9-15):

```python
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.replay.validators import validate_event_type
```

```python
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import AgentRun, AgentTraceEvent
from src.replay.pairing import OperationPairingStatus, validate_operation_pairing
from src.replay.schemas import ReplayEventV3, ReplayResponseV3
from src.replay.validators import guard_redacted_payload, retention_for_event_type, validate_event_type
```

**Strict schema pattern** (`src/replay/schemas.py` lines 37-65):

```python
class ReplayEventV3(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["replay_event.v3"] = "replay_event.v3"
    event_id: UUID
    run_id: UUID
    tenant_id: UUID
    thread_id: str = Field(min_length=1)
    trace_id: str | None = None
    sequence: int = Field(gt=0)
    event_type: str
    occurred_at: datetime
    operation_id: UUID | None = None
    parent_operation_id: UUID | None = None
    attempt: int | None = Field(default=None, gt=0)
    node_name: str | None = None
    actor: dict[str, Any]
    resource_refs: dict[str, Any]
    redacted_payload: dict[str, Any]
    redaction_policy_version: str = Field(min_length=1)
    provenance: ReplayEventProvenance
    retention: ReplayRetention
    error: ReplayError | None = None

    @field_validator("event_type")
    @classmethod
    def _validate_event_type(cls, event_type: str) -> str:
        validate_event_type(event_type)
        return event_type
```

Copy this pattern for `DecisionEventEnvelopeV1`, but fix `schema_version` to `Literal["minimal_event_envelope.v1"]`, keep only the minimal envelope fields, and keep `model_config = ConfigDict(extra="forbid")`.

**Registered event + redaction guard pattern** (`src/replay/validators.py` lines 83-102):

```python
def validate_event_type(event_type: str) -> None:
    if event_type not in REPLAY_EVENT_TYPES:
        raise ValueError(f"event_type {event_type!r} is not registered for ReplayEventV3")


def guard_redacted_payload(redacted_payload: dict[str, Any]) -> None:
    """Reject unsafe keys before event persistence or projection."""

    def walk(value: Any, path: str) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                if key.lower() in FORBIDDEN_REDACTED_PAYLOAD_KEYS:
                    raise ValueError(f"{path} must not carry {key}")
                walk(child, f"{path}.{key}")
            return
        if isinstance(value, list):
            for index, child in enumerate(value):
                walk(child, f"{path}[{index}]")

    walk(redacted_payload, "redacted_payload")
```

Use the same recursive shape for `guard_resource_refs(resource_refs)`, with the path root changed to `"resource_refs"`.

**Emitter persistence pattern** (`src/replay/service.py` lines 49-82 and 138-140):

```python
async def append_event(
    self,
    *,
    run_id: uuid.UUID | str,
    tenant_id: uuid.UUID | str,
    thread_id: str,
    event_type: str,
    actor: dict[str, Any],
    resource_refs: dict[str, Any],
    redacted_payload: dict[str, Any],
    trace_id: str | None = None,
    operation_id: uuid.UUID | str | None = None,
    parent_operation_id: uuid.UUID | str | None = None,
    attempt: int | None = None,
    version: int | None = 1,
    node_name: str | None = None,
    approval_id: uuid.UUID | str | None = None,
    draft_id: uuid.UUID | str | None = None,
    tool_call_id: str | None = None,
    evidence_refs_json: list[dict[str, Any]] | None = None,
    error_json: dict[str, Any] | None = None,
    archived_at: datetime | None = None,
    retention_until: datetime | None = None,
    deleted_at: datetime | None = None,
    schema_version: str = "replay_event.v3",
    occurred_at: datetime | None = None,
    redaction_policy_version: str = "redaction.v1",
    iteration: int | None = None,
) -> dict[str, Any]:
    """Persist one event row and return its V3 projection."""
    validate_event_type(event_type)
    retention_class = retention_for_event_type(event_type)
    guard_redacted_payload(redacted_payload)
```

```python
if schema_version == "minimal_event_envelope.v1":
    return self.project_minimal_event(row)
return self.project_event(row, pairing_status=pairing_status)
```

`emit_decision_event(...)` should normalize and validate inputs, then call `ReplayService(session).append_event(..., schema_version="minimal_event_envelope.v1")` instead of inserting rows directly.

**Minimal projection shape** (`src/replay/service.py` lines 175-192):

```python
def project_minimal_event(self, event: AgentTraceEvent) -> dict[str, Any]:
    """Project stored rows into the Phase 10-14 minimal envelope shape."""
    return {
        "schema_version": event.schema_version,
        "event_id": event.event_id,
        "sequence": event.sequence,
        "operation_id": event.operation_id,
        "run_id": event.run_id,
        "tenant_id": event.tenant_id,
        "thread_id": event.thread_id,
        "trace_id": event.trace_id,
        "event_type": event.event_type,
        "occurred_at": event.occurred_at,
        "actor": event.actor,
        "resource_refs": event.resource_refs,
        "redaction_policy_version": event.redaction_policy_version,
        "redacted_payload": event.redacted_payload,
    }
```

Use this exact field set for `DecisionEventEnvelopeV1`; do not add top-level `policy_version`, `model_version`, or `tool_version`.

**Trusted ReplayContext pattern** (`src/platform/context_projections.py` lines 57-69 and 241-266):

```python
class ReplayContext(ProjectionMetadata):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["replay_context.v1"] = "replay_context.v1"
    tenant_id: str
    user_id: str
    role: str
    session_id: str | None = None
    thread_id: str
    run_id: str
    trace_id: str | None = None
    locale: str | None = None
```

```python
def project_to_replay_context(
    trusted: TrustedContext,
    *,
    policy_version: str | None = None,
    model_version: str | None = None,
    tool_version: str | None = None,
    artifact_ref: str | None = None,
    artifact_refs: list[str] | None = None,
) -> ReplayContext:
    return ReplayContext(
        tenant_id=trusted.tenant_id,
        user_id=trusted.user_id,
        role=trusted.role,
        session_id=trusted.session_id,
        thread_id=trusted.thread_id,
        run_id=trusted.run_id,
        trace_id=trusted.trace_id,
        locale=trusted.locale,
        **_metadata_kwargs(
            policy_version=policy_version,
            model_version=model_version,
            tool_version=tool_version,
            artifact_ref=artifact_ref,
            artifact_refs=artifact_refs,
        ),
    )
```

New emitter usage should prefer `ReplayContext` for `run_id`, `tenant_id`, `thread_id`, and `trace_id`. Place context versions under `redacted_payload["versions"]`.

**Operation event conditional validation pattern** (`src/replay/pairing.py` lines 12-17 and 146-155):

```python
STARTED_SUFFIXES = ("_started",)
TERMINAL_SUFFIXES = ("_completed", "_failed", "_unknown", "_expired", "_cancelled")


class OperationPairingError(ValueError):
    """Raised when a replay operation event violates pairing or retry rules."""
```

```python
def _is_operation_event(event_type: str) -> bool:
    return _is_started_event(event_type) or _is_terminal_event(event_type)


def _is_started_event(event_type: str) -> bool:
    return event_type.endswith(STARTED_SUFFIXES)


def _is_terminal_event(event_type: str) -> bool:
    return event_type.endswith(TERMINAL_SUFFIXES)
```

For Phase 28 minimal events, copy only the suffix-based operation classification and require `operation_id` for operation events. Do not copy V3-only `attempt` / `parent_operation_id` requirements into the minimal facade.

**No direct existing code analog:** reason-code normalization. Implement from decisions D-11 through D-15: accept legacy `reason_code`, normalize into `redacted_payload["reason_codes"]`, first-seen de-dupe, require non-empty snake_case, and do not sort.

---

### `src/replay/validators.py` (utility, transform / validation)

**Analogs:** `src/replay/validators.py`, `src/approvals/events.py`

**Forbidden-key registry pattern** (`src/replay/validators.py` lines 56-80):

```python
FORBIDDEN_REDACTED_PAYLOAD_KEYS: set[str] = {
    "data",
    "raw",
    "arguments",
    "prompt",
    "raw_prompt",
    "raw_args",
    "raw_payload",
    "raw_tool_output",
    "secret",
    "secrets",
    "credential",
    "credentials",
    "pii",
    "source_block_id",
    "source_block_ids",
    "document_block_id",
    "parser_metadata_json",
    "ocr_metadata_json",
    "rag_ingestion_job_id",
    "ingestion_job_id",
    "raw_parser_payload",
    "parser_dump",
    "hidden_text",
}
```

**Cross-field approval guard pattern** (`src/approvals/events.py` lines 222-231 and 343-352):

```python
def validate_approval_event_payload(
    *,
    metadata: Mapping[str, Any],
    resource_refs: Mapping[str, Any],
    redacted_payload: Mapping[str, Any],
) -> None:
    """Reject unsafe event keys across all persisted approval event JSON fields."""
    _guard_safe_mapping(metadata, "metadata_json")
    _guard_safe_mapping(resource_refs, "resource_refs_json")
    _guard_safe_mapping(redacted_payload, "redacted_payload_json")
```

```python
def _guard_safe_mapping(value: Any, path: str) -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            if key.lower() in FORBIDDEN_APPROVAL_EVENT_KEYS:
                raise ValueError(f"{path} must not carry {key}")
            _guard_safe_mapping(child, f"{path}.{key}")
        return
    if isinstance(value, list):
        for index, child in enumerate(value):
            _guard_safe_mapping(child, f"{path}[{index}]")
```

Use this cross-field idea to add `guard_resource_refs(...)` beside `guard_redacted_payload(...)`. Keep error messages path-specific so tests can assert whether leakage came from payload or refs.

---

### `src/replay/service.py` (service, event-driven + CRUD)

**Analog:** `src/replay/service.py`

**Append validation and allocator pattern** (lines 79-107):

```python
validate_event_type(event_type)
retention_class = retention_for_event_type(event_type)
guard_redacted_payload(redacted_payload)

safe_payload = dict(redacted_payload)
if iteration is not None:
    safe_payload["iteration"] = iteration
if schema_version == "replay_event.v3":
    safe_payload.setdefault("retention_class", retention_class)

run_uuid = _as_uuid(run_id)
await self._lock_run(run_uuid)
existing_events = await self._events_for_run(run_uuid)
pairing_status: OperationPairingStatus | None = None
if schema_version == "replay_event.v3":
    pairing_result = validate_operation_pairing(
        existing_events,
        {
            "event_type": event_type,
            "operation_id": operation_id,
            "parent_operation_id": parent_operation_id,
            "attempt": attempt,
            "redacted_payload": safe_payload,
        },
    )
    pairing_status = pairing_result.pairing_status

sequence = await self._next_sequence_for_run(run_uuid)
event_id = uuid.uuid5(uuid.NAMESPACE_URL, f"{run_uuid}:{sequence}")
```

Add `guard_resource_refs(resource_refs)` alongside `guard_redacted_payload(redacted_payload)` before row construction.

**Row persistence pattern** (lines 108-140):

```python
row = AgentTraceEvent(
    event_id=event_id,
    run_id=run_uuid,
    sequence=sequence,
    operation_id=_as_uuid(operation_id) if operation_id is not None else None,
    parent_operation_id=_as_uuid(parent_operation_id) if parent_operation_id is not None else None,
    attempt=attempt,
    version=version,
    node_name=node_name,
    approval_id=_as_uuid(approval_id) if approval_id is not None else None,
    draft_id=_as_uuid(draft_id) if draft_id is not None else None,
    tool_call_id=tool_call_id,
    evidence_refs_json=evidence_refs_json,
    error_json=error_json,
    tenant_id=_as_uuid(tenant_id),
    thread_id=thread_id,
    trace_id=trace_id,
    event_type=event_type,
    schema_version=schema_version,
    occurred_at=occurred_at or datetime.now(UTC),
    actor=actor,
    resource_refs=resource_refs,
    redaction_policy_version=redaction_policy_version,
    redacted_payload=safe_payload,
    archived_at=archived_at,
    retention_until=retention_until,
    deleted_at=deleted_at,
)
self.session.add(row)
await self.session.flush()
if schema_version == "minimal_event_envelope.v1":
    return self.project_minimal_event(row)
return self.project_event(row, pairing_status=pairing_status)
```

Preserve `ReplayService.append_event(...)` as the persistence boundary. `project_minimal_event(...)` should validate through `DecisionEventEnvelopeV1` after the new schema exists.

---

### `src/agent/events.py` (utility / compatibility wrapper, event-driven)

**Analog:** `src/agent/events.py`

**Current imports and public constants pattern** (lines 10-23):

```python
from src.replay import (
    FORBIDDEN_REDACTED_PAYLOAD_KEYS as _REPLAY_FORBIDDEN_REDACTED_PAYLOAD_KEYS,
    REPLAY_EVENT_TYPES,
    ReplayService,
    guard_redacted_payload,
)


TOOL_CALL_TOOLS = {"get_order", "get_refund_case", "get_ticket", "get_logistics", "get_merchant_risk"}
RAG_RETRIEVAL_TOOLS = {"search_policy", "search_sop", "search_case_memory"}
MINIMAL_EVENT_TYPES = set(REPLAY_EVENT_TYPES)
EVENT_RETENTION_CLASSIFICATION = {event_type: "minimal_event" for event_type in MINIMAL_EVENT_TYPES}
SCHEMA_VERSION = "minimal_event_envelope.v1"
FORBIDDEN_REDACTED_PAYLOAD_KEYS = set(_REPLAY_FORBIDDEN_REDACTED_PAYLOAD_KEYS)
```

Keep these compatibility constants unless the planner explicitly migrates imports to `src.replay`.

**Wrapper signature and delegation pattern** (lines 40-72):

```python
async def emit_event(
    session: AsyncSession,
    *,
    run_id: uuid.UUID | str,
    tenant_id: uuid.UUID | str,
    thread_id: str,
    event_type: str,
    actor: dict[str, Any],
    resource_refs: dict[str, Any],
    redacted_payload: dict[str, Any],
    trace_id: str | None = None,
    operation_id: uuid.UUID | str | None = None,
    iteration: int | None = None,
    redaction_policy_version: str = "redaction.v1",
) -> dict[str, Any]:
    """Persist and return one minimal event envelope."""
    if event_type not in MINIMAL_EVENT_TYPES:
        raise ValueError(f"event_type {event_type!r} is not registered for the minimal envelope")

    return await ReplayService(session).append_event(
        run_id=run_id,
        tenant_id=tenant_id,
        thread_id=thread_id,
        event_type=event_type,
        actor=actor,
        resource_refs=resource_refs,
        redacted_payload=redacted_payload,
        trace_id=trace_id,
        operation_id=operation_id,
        iteration=iteration,
        redaction_policy_version=redaction_policy_version,
        schema_version=SCHEMA_VERSION,
    )
```

Change only the target of delegation: call `src.replay.decision_events.emit_decision_event(...)` and preserve existing parameters. If adding `reason_code` / `reason_codes`, make them keyword-only optional to avoid breaking existing callers.

**Existing caller shape** (`src/agent/nodes/investigate.py` lines 452-464):

```python
await emit_event(
    session,
    run_id=tool_ctx.run_id,
    tenant_id=tool_ctx.tenant_id,
    thread_id=tool_ctx.thread_id,
    event_type=event_type,
    actor={"type": "agent", "id": "moca"},
    resource_refs={"tool": descriptor.name if descriptor is not None else "unknown"},
    redacted_payload=redacted_payload,
    trace_id=tool_ctx.trace_id,
    operation_id=operation_id,
    iteration=iteration,
)
```

Preserve this call shape for tool/RAG writers.

**Current fail-open memory seam** (`src/agent/nodes/memory_write.py` lines 315-340):

```python
async def _emit_memory_event(
    state: AgentState,
    configurable: dict[str, Any],
    session: Any,
    event_type: str,
    payload: dict[str, Any],
) -> None:
    run_id = state.get("current_run_id")
    tenant_id = state.get("tenant_id")
    thread_id = state.get("thread_id")
    if not run_id or not tenant_id or not thread_id:
        return
    try:
        await emit_event(
            session,
            run_id=run_id,
            tenant_id=tenant_id,
            thread_id=str(thread_id),
            event_type=event_type,
            actor={"type": "agent", "id": "moca"},
            resource_refs={"memory_type": "session_memory"},
            redacted_payload={key: value for key, value in payload.items() if value is not None},
            trace_id=configurable.get("trace_id"),
        )
    except Exception:
        return
```

Planner note: this is a known compatibility risk from research. Phase 28 should at least test wrapper-level fail-closed behavior for missing identity; avoid broad memory domain rewrites unless the plan explicitly scopes them.

---

### `src/replay/__init__.py` (package export / config, transform)

**Analog:** `src/replay/__init__.py`

**Barrel import pattern** (lines 3-21):

```python
from src.replay.pairing import OperationPairingError
from src.replay.pairing import OperationPairingResult
from src.replay.pairing import OperationPairingStatus
from src.replay.pairing import STARTED_SUFFIXES
from src.replay.pairing import TERMINAL_SUFFIXES
from src.replay.pairing import validate_operation_pairing
from src.replay.lifecycle import RunLifecycleService
from src.replay.schemas import ReplayError
from src.replay.schemas import ReplayEventProvenance
from src.replay.schemas import ReplayEventV3
from src.replay.schemas import ReplayResponseV3
from src.replay.schemas import ReplayRetention
from src.replay.service import ReplayService
from src.replay.validators import EVENT_RETENTION_CLASSIFICATION
from src.replay.validators import FORBIDDEN_REDACTED_PAYLOAD_KEYS
from src.replay.validators import REPLAY_EVENT_TYPES
from src.replay.validators import guard_redacted_payload
from src.replay.validators import retention_for_event_type
from src.replay.validators import validate_event_type
```

**`__all__` pattern** (lines 23-43):

```python
__all__ = [
    "EVENT_RETENTION_CLASSIFICATION",
    "FORBIDDEN_REDACTED_PAYLOAD_KEYS",
    "OperationPairingError",
    "OperationPairingResult",
    "OperationPairingStatus",
    "REPLAY_EVENT_TYPES",
    "ReplayError",
    "ReplayEventProvenance",
    "ReplayEventV3",
    "ReplayResponseV3",
    "ReplayRetention",
    "ReplayService",
    "RunLifecycleService",
    "STARTED_SUFFIXES",
    "TERMINAL_SUFFIXES",
    "guard_redacted_payload",
    "retention_for_event_type",
    "validate_operation_pairing",
    "validate_event_type",
]
```

Export `DecisionEventEnvelopeV1`, `emit_decision_event`, and any intentionally public guard/normalization helper by following this exact import + `__all__` style.

---

### `tests/replay/test_decision_events.py` (test, event-driven + CRUD)

**Analogs:** `tests/replay/test_replay_service.py`, `tests/agent/test_events.py`, `tests/platform/test_context_projections.py`

**Import/test style pattern** (`tests/replay/test_replay_service.py` lines 1-21):

```python
from __future__ import annotations

from datetime import UTC, datetime
import uuid

import pytest
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.agent.trace import write_agent_run
from src.db.models import AgentRun, AgentTraceEvent
from src.replay.pairing import OperationPairingError
from src.replay.schemas import (
    ReplayEventProvenance,
    ReplayEventV3,
    ReplayResponseV3,
    ReplayRetention,
)
from src.replay.service import ReplayService
from src.replay.validators import REPLAY_EVENT_TYPES, retention_for_event_type, validate_event_type
```

Use this pytest style and import `DecisionEventEnvelopeV1`, `emit_decision_event`, and `ReplayContext` as needed.

**Base payload / strict schema pattern** (`tests/replay/test_replay_service.py` lines 24-55 and 110-124):

```python
def _base_event_payload() -> dict:
    run_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    return {
        "event_id": uuid.uuid4(),
        "run_id": run_id,
        "tenant_id": tenant_id,
        "thread_id": "thread-replay-001",
        "trace_id": "trace-replay-001",
        "sequence": 1,
        "event_type": "node_started",
        "occurred_at": datetime(2026, 6, 16, 10, 0, tzinfo=UTC),
        "operation_id": uuid.uuid4(),
        "parent_operation_id": None,
        "attempt": 1,
        "node_name": "investigate",
        "actor": {"type": "agent", "id": "moca"},
        "resource_refs": {"evidence_ids": ["policy_refund_timeout/chunk_001@v3"]},
        "redacted_payload": {"status": "started", "summary": "investigation started"},
        "redaction_policy_version": "redaction.v1",
        "provenance": {
            "source_schema_version": "replay_event.v3",
            "pairing_status": "paired",
        },
        "retention": {
            "archived_at": None,
            "retention_until": None,
            "deleted_at": None,
        },
        "error": None,
    }
```

```python
def test_replay_schemas_are_strict():
    payload = _base_event_payload()
    payload["unexpected"] = "not allowed"

    with pytest.raises(ValidationError):
        ReplayEventV3(**payload)

    with pytest.raises(ValidationError):
        ReplayEventProvenance(
            source_schema_version="minimal_event_envelope.v1",
            pairing_status="invented",
        )

    with pytest.raises(ValidationError):
        ReplayRetention(archived_at=None, retention_until=None, deleted_at=None, extra=True)
```

Copy this style for `DecisionEventEnvelopeV1`: a minimal base payload, valid model assertion, extra-key rejection, invalid event type rejection, invalid `reason_codes`, and missing `operation_id` for operation event types.

**DB integration helper pattern** (`tests/agent/test_events.py` lines 24-41):

```python
async def _create_run(session: AsyncSession) -> tuple[uuid.UUID, uuid.UUID]:
    run_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    now = datetime.now(UTC)
    await write_agent_run(
        session,
        run_id=str(run_id),
        thread_id="event-test-thread",
        tenant_id=str(tenant_id),
        user_id=str(uuid.uuid4()),
        input_query="订单退款为什么超时？",
        final_status="completed",
        final_response="根据政策建议核实退款通道。",
        started_at=now,
        completed_at=now,
        total_latency_ms=12,
    )
    return run_id, tenant_id
```

Use this helper for emitter integration tests that persist through `ReplayService.append_event(...)`.

**Redaction negative test pattern** (`tests/agent/test_events.py` lines 280-335):

```python
@pytest.mark.asyncio
async def test_redaction_guard(session: AsyncSession):
    run_id, tenant_id = await _create_run(session)

    with pytest.raises(ValueError):
        await _emit(
            session,
            run_id=run_id,
            tenant_id=tenant_id,
            redacted_payload={"data": {"raw": "tool output"}},
        )
```

Add matching negative tests for `resource_refs`, for example `resource_refs={"raw_payload": {"customer_phone": "..."}}` must raise and must not persist.

---

### `tests/agent/test_events.py` (test, event-driven)

**Analog:** `tests/agent/test_events.py`

**Wrapper delegation spy pattern** (lines 78-128):

```python
@pytest.mark.asyncio
async def test_emit_event_delegates_to_replay_service(monkeypatch):
    calls = []

    class SpyReplayService:
        def __init__(self, session):
            self.session = session

        async def append_event(self, **kwargs):
            calls.append(kwargs)
            return {
                "schema_version": "minimal_event_envelope.v1",
                "event_id": uuid.uuid4(),
                "sequence": 7,
                "operation_id": kwargs.get("operation_id"),
                "run_id": uuid.UUID(str(kwargs["run_id"])),
                "tenant_id": uuid.UUID(str(kwargs["tenant_id"])),
                "thread_id": kwargs["thread_id"],
                "trace_id": kwargs.get("trace_id"),
                "event_type": kwargs["event_type"],
                "occurred_at": datetime.now(UTC),
                "actor": kwargs["actor"],
                "resource_refs": kwargs["resource_refs"],
                "redaction_policy_version": kwargs["redaction_policy_version"],
                "redacted_payload": {
                    **kwargs["redacted_payload"],
                    "iteration": kwargs["iteration"],
                },
            }

    monkeypatch.setattr(events_module, "ReplayService", SpyReplayService)
```

Update this test to spy on `emit_decision_event(...)` instead of `ReplayService` after the wrapper delegates to the replay-owned facade.

**Event registry tests pattern** (lines 197-226):

```python
def test_memory_write_event_types_and_retention_are_registered():
    assert {"memory_write_started", "memory_write_completed", "memory_write_failed"} <= MINIMAL_EVENT_TYPES
    assert EVENT_RETENTION_CLASSIFICATION["memory_write_started"] == "minimal_event"
    assert EVENT_RETENTION_CLASSIFICATION["memory_write_completed"] == "minimal_event"
    assert EVENT_RETENTION_CLASSIFICATION["memory_write_failed"] == "minimal_event"


def test_approval_event_types_and_retention_are_registered():
    assert {"approval_requested", "approval_decided", "approval_expired", "approval_resumed"} <= MINIMAL_EVENT_TYPES
    assert EVENT_RETENTION_CLASSIFICATION["approval_requested"] == "minimal_event"
    assert EVENT_RETENTION_CLASSIFICATION["approval_decided"] == "minimal_event"
    assert EVENT_RETENTION_CLASSIFICATION["approval_expired"] == "minimal_event"
    assert EVENT_RETENTION_CLASSIFICATION["approval_resumed"] == "minimal_event"
```

Keep these compatibility tests passing while adding legacy `reason_code` to `reason_codes` conversion tests.

---

### `tests/replay/test_sequence_allocator.py` (test, event-driven + CRUD)

**Analog:** `tests/replay/test_sequence_allocator.py`

**Concurrency allocator pattern** (lines 74-101):

```python
@pytest.mark.asyncio
async def test_concurrent_append_calls_do_not_duplicate_sequence(test_engine):
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as setup_session:
        run_id, tenant_id = await _create_run(setup_session)
        await setup_session.commit()

    async def append_from_writer(index: int) -> int:
        async with session_factory() as worker_session:
            event = await ReplayService(worker_session).append_event(
                run_id=run_id,
                tenant_id=tenant_id,
                thread_id="sequence-allocator-thread",
                event_type="tool_call_started",
                actor={"type": "agent", "id": f"writer-{index}"},
                resource_refs={"tool": "get_order"},
                redacted_payload={"status": "started", "writer_index": index},
                operation_id=uuid.uuid4(),
                attempt=1,
                schema_version="replay_event.v3",
            )
            await worker_session.commit()
            return int(event["sequence"])

    sequences = await asyncio.gather(*(append_from_writer(index) for index in range(5)))

    assert sorted(sequences) == [2, 3, 4, 5, 6]
    assert len(sequences) == len(set(sequences)), "duplicate sequence values are forbidden"
```

Preserve this unchanged unless adding an `emit_decision_event(...)` writer path needs a new case.

**Shared writer coverage pattern** (lines 165-257):

```python
@pytest.mark.asyncio
async def test_sequence_allocator_covers_pre_lifecycle_writer_surfaces(session: AsyncSession):
    run_id, tenant_id = await _create_run(session)

    # graph writer: src.agent.events.emit_event
    graph_writer = await emit_event(
        session,
        run_id=run_id,
        tenant_id=tenant_id,
        thread_id="sequence-allocator-thread",
        event_type="node_started",
        actor={"type": "agent", "id": "graph-writer"},
        resource_refs={"node": "investigate"},
        redacted_payload={"status": "started"},
    )
```

Add the replay-owned `emit_decision_event(...)` facade to this shared writer test if the planner wants explicit allocator coverage for the new entrypoint. Keep the final sequence assertions monotonic and contiguous.

---

### `tests/platform/test_context_projections.py` (test, transform)

**Analog:** `tests/platform/test_context_projections.py`

**TrustedContext fixture pattern** (lines 22-34):

```python
def _trusted_context() -> TrustedContext:
    return TrustedContext(
        tenant_id="tenant-1",
        user_id="user-1",
        role="support",
        permissions=["tool:get_order", "knowledge:search"],
        merchant_scope=MerchantScopeV1(merchant_ids=["merchant-1"]),
        session_id="session-1",
        thread_id="thread-1",
        run_id="run-1",
        trace_id="trace-1",
        locale="zh-CN",
    )
```

**Projection-local metadata pattern** (lines 124-154):

```python
def test_memory_approval_replay_intent_projections_do_not_widen_identity_scope() -> None:
    trusted = _trusted_context()
    metadata = {
        "policy_version": "policy.v1",
        "model_version": "gpt-test.v1",
        "tool_version": "tool.v2",
        "artifact_refs": ["artifact-1"],
    }

    projections = [
        project_to_memory_context(trusted, **metadata),
        project_to_approval_context(trusted, approval_ref="approval-1", safety_snapshot_ref="safety-1", **metadata),
        project_to_replay_context(trusted, **metadata),
        project_to_intent_policy_context(trusted, channel="agent_runs", **metadata),
    ]

    for projection in projections:
        payload = projection.model_dump()
        assert payload["tenant_id"] == trusted.tenant_id
        assert payload["user_id"] == trusted.user_id
        assert payload["role"] == trusted.role
        assert payload["thread_id"] == trusted.thread_id
        assert payload["run_id"] == trusted.run_id
        assert payload["trace_id"] == trusted.trace_id
        assert payload.get("permissions") in (None, trusted.permissions)
        assert payload.get("merchant_scope") in (None, trusted.merchant_scope.model_dump(), ["merchant-1"])

    canonical_payload = trusted.model_dump()
    for local_field in ("policy_version", "model_version", "tool_version", "artifact_ref", "artifact_refs"):
        assert local_field not in canonical_payload
```

If this file is touched, keep it focused on projection-local metadata and no TrustedContext widening. Event-specific placement under `redacted_payload.versions` belongs in `tests/replay/test_decision_events.py`.

---

### `tests/replay/test_replay_service.py` (test, event-driven + CRUD)

**Analog:** `tests/replay/test_replay_service.py`

**Minimal-to-V3 projection pattern** (lines 422-449):

```python
@pytest.mark.asyncio
async def test_replay_service_projects_minimal_row_as_unresolved_without_backwrite(session: AsyncSession):
    run_id, tenant_id = await _create_run(session)
    row = AgentTraceEvent(
        event_id=uuid.uuid4(),
        run_id=run_id,
        sequence=2,
        tenant_id=tenant_id,
        thread_id="thread-replay-service",
        event_type="approval_requested",
        schema_version="minimal_event_envelope.v1",
        occurred_at=datetime.now(UTC),
        actor={"type": "approver", "id": "approval-service"},
        resource_refs={"approval_id": str(uuid.uuid4())},
        redaction_policy_version="redaction.v1",
        redacted_payload={"status": "pending"},
    )
    session.add(row)
    await session.flush()

    projected = ReplayService(session).project_event(row)

    assert projected["schema_version"] == "replay_event.v3"
    assert projected["provenance"] == {
        "source_schema_version": "minimal_event_envelope.v1",
        "pairing_status": "unresolved",
    }
    assert row.schema_version == "minimal_event_envelope.v1"
```

Add or move a test asserting `ReplayService.project_minimal_event(row)` validates through `DecisionEventEnvelopeV1` and returns exactly the minimal envelope keys. Do not backwrite minimal rows to V3.

## Shared Patterns

### Strict Contract Schemas

**Source:** `src/replay/schemas.py` lines 37-65
**Apply to:** `src/replay/decision_events.py`, `tests/replay/test_decision_events.py`

Use Pydantic v2 with `model_config = ConfigDict(extra="forbid")`, literal schema version, field constraints, and `@field_validator("event_type")` calling `validate_event_type(...)`.

### Event Persistence

**Source:** `src/replay/service.py` lines 49-140
**Apply to:** `src/replay/decision_events.py`, `src/agent/events.py`, sequence tests

All production event writes should go through `ReplayService.append_event(...)`. Do not insert `AgentTraceEvent` directly outside tests.

### Minimal Envelope Field Set

**Source:** `src/replay/service.py` lines 175-192
**Apply to:** `DecisionEventEnvelopeV1`, `project_minimal_event(...)`, wrapper return-shape tests

The minimal envelope top-level keys are exactly: `schema_version`, `event_id`, `sequence`, `operation_id`, `run_id`, `tenant_id`, `thread_id`, `trace_id`, `event_type`, `occurred_at`, `actor`, `resource_refs`, `redaction_policy_version`, and `redacted_payload`.

### Trusted Identity And Version Metadata

**Source:** `src/platform/context_projections.py` lines 57-69 and 241-266
**Apply to:** `emit_decision_event(...)`, `tests/replay/test_decision_events.py`, `tests/platform/test_context_projections.py`

Prefer `ReplayContext` for trusted `run_id`, `tenant_id`, `thread_id`, and `trace_id`. Keep policy/model/tool version fields projection-local and copy them into `redacted_payload.versions`, not the envelope top level.

### Recursive Redaction For Payload And Refs

**Source:** `src/replay/validators.py` lines 56-102; `src/approvals/events.py` lines 222-231 and 343-352
**Apply to:** `src/replay/validators.py`, `src/replay/decision_events.py`, `src/replay/service.py`, redaction tests

Reuse the existing forbidden-key set and recursive walker. Add resource-ref coverage so unsafe keys cannot bypass through `resource_refs`.

### Stable Resource References

**Source:** `src/approvals/events.py` lines 305-328; `src/actions/service.py` lines 248-268; `tests/agent/test_tools/test_create_coupon_grant_draft.py` lines 601-644
**Apply to:** decision-event facade validation and tests

Approval/action refs use typed refs, ids, and hashes:

```python
refs: dict[str, Any] = {
    "request_ref": f"approval_request:{request.id}:r{request.revision}",
    "revision_ref": approval_revision_ref(request),
    "request_version": request.version,
    "action_payload_hash": request.action_payload_hash,
    "safety_snapshot_ref": request.safety_snapshot_ref,
    "safety_snapshot_hash": request.safety_snapshot_hash,
}
```

```python
resource_refs={
    "draft_id": str(draft_id),
    "target_id": target_id,
    "action_payload_hash": action_payload_hash,
    "safety_snapshot_hash": safety_snapshot_hash,
}
```

Tests already assert no raw payload or arguments leak:

```python
assert "payload" not in event.resource_refs
assert "payload" not in event.redacted_payload
assert "arguments" not in event.redacted_payload
```

### Compatibility Wrapper

**Source:** `src/agent/events.py` lines 40-72; `tests/agent/test_events.py` lines 78-128
**Apply to:** `src/agent/events.py`, `tests/agent/test_events.py`

Preserve old call signatures and return dict shape while moving the implementation behind `emit_decision_event(...)`.

### Reason-Code Normalization Gap

**Source:** decisions in `28-CONTEXT.md` lines 36-39; existing singular producers in `src/replay/lifecycle.py` lines 197-216 and `src/agent/nodes/memory_write.py` lines 242-303
**Apply to:** `src/replay/decision_events.py`, `src/agent/events.py`, tests

No existing code implements the desired first-seen plural normalization. Current producers write singular `reason_code`:

```python
payload: dict[str, Any] = {
    "status": status,
    "previous_status": previous_status,
    "reason_code": reason_code,
}
```

```python
result = {
    "status": "skipped",
    "decision": "skip",
    "reason_code": reason_code,
    "pii_classification": "none",
}
```

Implement the new normalization in the facade/wrapper seam, then update tests to assert stored/returned payloads use `reason_codes`.

## No Analog Found

| File / Pattern | Role | Data Flow | Reason |
|----------------|------|-----------|--------|
| Reason-code first-seen de-dup helper | utility | transform | Existing code only has singular `reason_code` producers; implement from Phase 28 decisions D-11 through D-15. |

## Metadata

**Analog search scope:** `src/replay`, `src/agent`, `src/platform`, `src/approvals`, `src/actions`, `tests/replay`, `tests/agent`, `tests/platform`
**Files scanned:** 22
**Pattern extraction date:** 2026-06-23

