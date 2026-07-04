from __future__ import annotations

from types import SimpleNamespace
import uuid

import pytest

from src.replay.pairing import (
    OperationPairingError,
    OperationPairingStatus,
    validate_operation_pairing,
)


def _event(
    event_type: str,
    *,
    operation_id: uuid.UUID | None = None,
    parent_operation_id: uuid.UUID | None = None,
    attempt: int | None = 1,
    iteration: int | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        event_type=event_type,
        operation_id=operation_id,
        parent_operation_id=parent_operation_id,
        attempt=attempt,
        redacted_payload={} if iteration is None else {"iteration": iteration},
    )


def test_tool_call_started_then_completed_pair_is_valid():
    operation_id = uuid.uuid4()
    started = _event("tool_call_started", operation_id=operation_id)
    completed = _event("tool_call_completed", operation_id=operation_id)

    result = validate_operation_pairing([started], completed)

    assert result.pairing_status == OperationPairingStatus.PAIRED
    assert result.operation_id == operation_id


def test_duplicate_terminal_event_is_rejected():
    operation_id = uuid.uuid4()
    started = _event("tool_call_started", operation_id=operation_id)
    completed = _event("tool_call_completed", operation_id=operation_id)

    with pytest.raises(OperationPairingError, match="duplicate terminal"):
        validate_operation_pairing([started, completed], _event("tool_call_failed", operation_id=operation_id))


def test_started_event_without_terminal_reports_unresolved_status():
    operation_id = uuid.uuid4()

    result = validate_operation_pairing([], _event("tool_call_started", operation_id=operation_id))

    assert result.pairing_status == OperationPairingStatus.UNRESOLVED
    assert result.reason == "terminal_event_not_seen"


def test_retry_uses_new_operation_id_parent_operation_id_and_incremented_attempt():
    parent_operation_id = uuid.uuid4()
    retry_operation_id = uuid.uuid4()
    parent_started = _event("tool_call_started", operation_id=parent_operation_id, attempt=1)
    parent_failed = _event("tool_call_failed", operation_id=parent_operation_id, attempt=1)
    retry_started = _event(
        "tool_call_started",
        operation_id=retry_operation_id,
        parent_operation_id=parent_operation_id,
        attempt=2,
    )

    result = validate_operation_pairing([parent_started, parent_failed], retry_started)

    assert result.pairing_status == OperationPairingStatus.UNRESOLVED
    assert result.parent_operation_id == parent_operation_id
    assert result.attempt == 2


def test_retry_with_same_operation_id_is_rejected():
    operation_id = uuid.uuid4()
    started = _event("tool_call_started", operation_id=operation_id, attempt=1)
    failed = _event("tool_call_failed", operation_id=operation_id, attempt=1)

    with pytest.raises(OperationPairingError, match="same operation_id"):
        validate_operation_pairing(
            [started, failed],
            _event(
                "tool_call_started",
                operation_id=operation_id,
                parent_operation_id=operation_id,
                attempt=2,
            ),
        )


def test_missing_operation_id_or_attempt_is_rejected_for_operation_events():
    with pytest.raises(OperationPairingError, match="operation_id"):
        validate_operation_pairing([], _event("tool_call_started", operation_id=None, attempt=1))

    with pytest.raises(OperationPairingError, match="attempt"):
        validate_operation_pairing([], _event("tool_call_started", operation_id=uuid.uuid4(), attempt=None))

    with pytest.raises(OperationPairingError, match="attempt"):
        validate_operation_pairing([], _event("tool_call_started", operation_id=uuid.uuid4(), attempt=0))


def test_terminal_without_known_started_event_is_rejected():
    with pytest.raises(OperationPairingError, match="started"):
        validate_operation_pairing([], _event("tool_call_completed", operation_id=uuid.uuid4(), attempt=1))


def test_bounded_investigate_loop_events_preserve_iteration_values():
    first_operation_id = uuid.uuid4()
    second_operation_id = uuid.uuid4()
    first_started = _event("rag_retrieval_started", operation_id=first_operation_id, iteration=1)
    second_started = _event("tool_call_started", operation_id=second_operation_id, iteration=2)

    first = validate_operation_pairing([], first_started)
    second = validate_operation_pairing([first_started], second_started)

    assert first.iteration == 1
    assert second.iteration == 2


def test_bounded_investigate_loop_operations_share_parent_but_keep_distinct_identity_and_iteration():
    node_operation_id = uuid.uuid4()
    first_operation_id = uuid.uuid4()
    second_operation_id = uuid.uuid4()
    first_started = _event(
        "tool_call_started",
        operation_id=first_operation_id,
        parent_operation_id=node_operation_id,
        iteration=1,
    )
    first_completed = _event(
        "tool_call_completed",
        operation_id=first_operation_id,
        parent_operation_id=node_operation_id,
        iteration=1,
    )
    second_started = _event(
        "rag_retrieval_started",
        operation_id=second_operation_id,
        parent_operation_id=node_operation_id,
        iteration=2,
    )
    second_completed = _event(
        "rag_retrieval_completed",
        operation_id=second_operation_id,
        parent_operation_id=node_operation_id,
        iteration=2,
    )

    first_pair = validate_operation_pairing([first_started], first_completed)
    second_start = validate_operation_pairing([first_started, first_completed], second_started)
    second_pair = validate_operation_pairing(
        [first_started, first_completed, second_started],
        second_completed,
    )

    assert first_pair.operation_id == first_operation_id
    assert second_start.operation_id == second_operation_id
    assert second_pair.operation_id == second_operation_id
    assert {first_pair.parent_operation_id, second_start.parent_operation_id, second_pair.parent_operation_id} == {
        node_operation_id
    }
    assert first_pair.iteration == 1
    assert second_start.iteration == 2
    assert second_pair.iteration == 2
