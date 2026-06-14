from __future__ import annotations

from datetime import UTC, datetime, timedelta
import uuid

import pytest
from pydantic import ValidationError

from src.memory.schemas import SessionSlotV1, SessionSlotsEnvelopeV1


def test_session_slots_envelope_requires_schema_version() -> None:
    slot = SessionSlotV1(
        value="ORD-1001",
        source="explicit_user",
        source_run_id=str(uuid.uuid4()),
        updated_at=datetime.now(UTC),
        expires_at=datetime.now(UTC) + timedelta(minutes=30),
        compatible_intents=["refund_troubleshooting"],
    )

    envelope = SessionSlotsEnvelopeV1(slots={"order_id": slot})

    assert envelope.schema_version == "session_slots.v1"
    assert envelope.slots["order_id"].value == "ORD-1001"

    with pytest.raises(ValidationError):
        SessionSlotsEnvelopeV1.model_validate(
            {
                "schema_version": "session_slots.v0",
                "slots": {"order_id": slot.model_dump(mode="json")},
            }
        )


def test_session_slot_requires_value_source_run_and_expiry() -> None:
    slot = SessionSlotV1(
        value="ORD-1001",
        source="explicit_user",
        source_run_id=str(uuid.uuid4()),
        updated_at=datetime.now(UTC),
        expires_at=datetime.now(UTC) + timedelta(minutes=30),
        compatible_intents=["refund_troubleshooting"],
    )

    assert slot.value == "ORD-1001"
    assert slot.source == "explicit_user"
    assert slot.compatible_intents == ["refund_troubleshooting"]

    with pytest.raises(ValidationError):
        SessionSlotV1.model_validate(
            {
                "value": "ORD-1001",
                "source": "trusted_session_memory",
                "source_run_id": str(uuid.uuid4()),
                "updated_at": datetime.now(UTC).isoformat(),
                "expires_at": (datetime.now(UTC) + timedelta(minutes=30)).isoformat(),
                "compatible_intents": ["refund_troubleshooting"],
            }
        )
