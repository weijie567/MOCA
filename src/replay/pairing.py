"""Operation pairing and retry validation for ReplayEventV3."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any
import uuid


STARTED_SUFFIXES = ("_started",)
TERMINAL_SUFFIXES = ("_completed", "_failed", "_unknown", "_expired", "_cancelled")


class OperationPairingError(ValueError):
    """Raised when a replay operation event violates pairing or retry rules."""


class OperationPairingStatus(StrEnum):
    PAIRED = "paired"
    UNRESOLVED = "unresolved"
    NOT_APPLICABLE = "not_applicable"


@dataclass(frozen=True)
class OperationPairingResult:
    pairing_status: OperationPairingStatus
    operation_id: uuid.UUID | None
    parent_operation_id: uuid.UUID | None
    attempt: int | None
    reason: str
    iteration: int | None = None


def validate_operation_pairing(
    existing_events: Iterable[Any],
    candidate_event: Any,
) -> OperationPairingResult:
    """Validate a candidate operation event against prior run events."""
    event_type = str(_field(candidate_event, "event_type") or "")
    if not _is_operation_event(event_type):
        return OperationPairingResult(
            pairing_status=OperationPairingStatus.NOT_APPLICABLE,
            operation_id=_optional_uuid(_field(candidate_event, "operation_id")),
            parent_operation_id=_optional_uuid(_field(candidate_event, "parent_operation_id")),
            attempt=_field(candidate_event, "attempt"),
            reason="not_operation_event",
            iteration=_iteration(candidate_event),
        )

    operation_id = _required_uuid(_field(candidate_event, "operation_id"), "operation_id")
    attempt = _field(candidate_event, "attempt")
    if not isinstance(attempt, int) or attempt <= 0:
        raise OperationPairingError("operation event attempt must be a positive integer")

    parent_operation_id = _optional_uuid(_field(candidate_event, "parent_operation_id"))
    prior_events = list(existing_events)
    _validate_retry_shape(prior_events, operation_id, parent_operation_id, attempt, event_type)

    if _is_terminal_event(event_type):
        started = _events_for_operation(prior_events, operation_id, predicate=_is_started_event)
        if not started:
            raise OperationPairingError("terminal event requires a known started event")
        terminal_events = _events_for_operation(prior_events, operation_id, predicate=_is_terminal_event)
        if terminal_events:
            raise OperationPairingError("duplicate terminal event for operation_id is forbidden")
        return OperationPairingResult(
            pairing_status=OperationPairingStatus.PAIRED,
            operation_id=operation_id,
            parent_operation_id=parent_operation_id,
            attempt=attempt,
            reason="terminal_paired",
            iteration=_iteration(candidate_event),
        )

    if _is_started_event(event_type):
        duplicate_starts = _events_for_operation(prior_events, operation_id, predicate=_is_started_event)
        if duplicate_starts:
            raise OperationPairingError("same operation_id cannot be reused for a retry")
        return OperationPairingResult(
            pairing_status=OperationPairingStatus.UNRESOLVED,
            operation_id=operation_id,
            parent_operation_id=parent_operation_id,
            attempt=attempt,
            reason="terminal_event_not_seen",
            iteration=_iteration(candidate_event),
        )

    return OperationPairingResult(
        pairing_status=OperationPairingStatus.NOT_APPLICABLE,
        operation_id=operation_id,
        parent_operation_id=parent_operation_id,
        attempt=attempt,
        reason="not_operation_event",
        iteration=_iteration(candidate_event),
    )


def _validate_retry_shape(
    existing_events: list[Any],
    operation_id: uuid.UUID,
    parent_operation_id: uuid.UUID | None,
    attempt: int,
    event_type: str,
) -> None:
    if attempt == 1:
        return
    if parent_operation_id is None:
        raise OperationPairingError("retry attempt requires parent_operation_id")
    if parent_operation_id == operation_id:
        raise OperationPairingError("retry must use a new operation_id; same operation_id is forbidden")

    parent_attempts = [
        int(parent_attempt)
        for event in existing_events
        if _optional_uuid(_field(event, "operation_id")) == parent_operation_id
        for parent_attempt in [_field(event, "attempt")]
        if isinstance(parent_attempt, int)
    ]
    if not parent_attempts:
        raise OperationPairingError("retry parent_operation_id must reference an existing operation")
    if attempt <= max(parent_attempts):
        raise OperationPairingError("retry attempt must be greater than parent attempt")

    existing_same_operation = [
        event for event in existing_events if _optional_uuid(_field(event, "operation_id")) == operation_id
    ]
    if existing_same_operation:
        if _is_terminal_event(event_type) and all(
            _is_started_event(str(_field(event, "event_type") or "")) for event in existing_same_operation
        ):
            return
        raise OperationPairingError("retry must use a new operation_id; same operation_id is forbidden")


def _events_for_operation(
    events: list[Any],
    operation_id: uuid.UUID,
    *,
    predicate: Any,
) -> list[Any]:
    return [
        event
        for event in events
        if _optional_uuid(_field(event, "operation_id")) == operation_id
        and predicate(str(_field(event, "event_type") or ""))
    ]


def _is_operation_event(event_type: str) -> bool:
    return _is_started_event(event_type) or _is_terminal_event(event_type)


def _is_started_event(event_type: str) -> bool:
    return event_type.endswith(STARTED_SUFFIXES)


def _is_terminal_event(event_type: str) -> bool:
    return event_type.endswith(TERMINAL_SUFFIXES)


def _field(event: Any, name: str) -> Any:
    if isinstance(event, dict):
        return event.get(name)
    return getattr(event, name, None)


def _iteration(event: Any) -> int | None:
    payload = _field(event, "redacted_payload")
    if not isinstance(payload, dict):
        return None
    iteration = payload.get("iteration")
    return iteration if isinstance(iteration, int) else None


def _required_uuid(value: Any, name: str) -> uuid.UUID:
    parsed = _optional_uuid(value)
    if parsed is None:
        raise OperationPairingError(f"operation event requires {name}")
    return parsed


def _optional_uuid(value: Any) -> uuid.UUID | None:
    if value is None:
        return None
    if isinstance(value, uuid.UUID):
        return value
    return uuid.UUID(str(value))
