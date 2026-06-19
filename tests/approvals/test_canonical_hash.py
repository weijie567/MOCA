from __future__ import annotations

from datetime import UTC, datetime

import pytest

from src.common.canonical_hash import CanonicalHashError, canonical_hash, canonical_json, hash_input_bytes


PROPOSED_ACTION_SCHEMA_VERSION = "proposed_action.v1"
PROPOSED_ACTION_ALLOWED_FIELDS = {
    "schema_version",
    "tenant_id",
    "run_id",
    "action_id",
    "action_type",
    "target_type",
    "target_id",
    "amount",
    "currency",
    "args",
    "reason",
    "evidence_refs",
}
EXPECTED_PROPOSED_ACTION_CANONICAL_JSON = (
    '{"action_id":"act-1","action_type":"issue_coupon","amount":"100.00",'
    '"args":{"coupon_type":"cash"},"currency":"CNY","evidence_refs":[{'
    '"chunk_id":"chunk_001","doc_key":"policy_refund_timeout",'
    '"evidence_id":"policy_refund_timeout/chunk_001@v3","policy_version":"v3",'
    '"rank":1,"retrieval_config_version":"knowledge-search@v2",'
    '"retrieved_at":"2026-06-05T00:00:00.000Z","schema_version":"evidence_ref.v1",'
    '"tenant_id":"tenant-1",'
    '"text_hash":"sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}],'
    '"reason":"refund delay compensation","run_id":"run-1",'
    '"schema_version":"proposed_action.v1","target_id":"RF-1",'
    '"target_type":"refund_case","tenant_id":"tenant-1"}'
)
EXPECTED_PROPOSED_ACTION_DIGEST = "sha256:508e649e1b169a9520f7eb76403b0e00c90c1b1c52e17a499fd7bcdce2473094"


def _proposed_action_fixture(**overrides):
    action = {
        "schema_version": PROPOSED_ACTION_SCHEMA_VERSION,
        "tenant_id": "tenant-1",
        "run_id": "run-1",
        "action_id": "act-1",
        "action_type": "issue_coupon",
        "target_type": "refund_case",
        "target_id": "RF-1",
        "amount": "100.00",
        "currency": "CNY",
        "args": {"coupon_type": "cash"},
        "reason": "refund delay compensation",
        "evidence_refs": [
            {
                "schema_version": "evidence_ref.v1",
                "tenant_id": "tenant-1",
                "evidence_id": "policy_refund_timeout/chunk_001@v3",
                "doc_key": "policy_refund_timeout",
                "chunk_id": "chunk_001",
                "policy_version": "v3",
                "text_hash": ("sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"),
                "retrieved_at": "2026-06-05T00:00:00.000Z",
                "retrieval_config_version": "knowledge-search@v2",
                "rank": 1,
            }
        ],
    }
    action.update(overrides)
    return action


def test_proposed_action_v1_has_frozen_canonical_json_hash_input_and_digest():
    value = _proposed_action_fixture()

    canonical = canonical_json(
        value,
        schema_version=PROPOSED_ACTION_SCHEMA_VERSION,
        allowed_fields=PROPOSED_ACTION_ALLOWED_FIELDS,
        nullable_fields={"amount", "currency"},
    )

    assert canonical == EXPECTED_PROPOSED_ACTION_CANONICAL_JSON
    assert hash_input_bytes(PROPOSED_ACTION_SCHEMA_VERSION, canonical) == (
        b"hash_profile.v1\nproposed_action.v1\n" + canonical.encode("utf-8")
    )
    assert (
        canonical_hash(
            value,
            schema_version=PROPOSED_ACTION_SCHEMA_VERSION,
            allowed_fields=PROPOSED_ACTION_ALLOWED_FIELDS,
            nullable_fields={"amount", "currency"},
        )
        == EXPECTED_PROPOSED_ACTION_DIGEST
    )


def test_unknown_fields_are_rejected():
    value = _proposed_action_fixture(unexpected="smuggled")

    with pytest.raises(CanonicalHashError, match="unknown"):
        canonical_json(
            value,
            schema_version=PROPOSED_ACTION_SCHEMA_VERSION,
            allowed_fields=PROPOSED_ACTION_ALLOWED_FIELDS,
            nullable_fields={"amount", "currency"},
        )


def test_bare_json_float_is_rejected():
    value = _proposed_action_fixture(args={"coupon_type": "cash", "score": 0.91})

    with pytest.raises(CanonicalHashError, match="float"):
        canonical_json(
            value,
            schema_version=PROPOSED_ACTION_SCHEMA_VERSION,
            allowed_fields=PROPOSED_ACTION_ALLOWED_FIELDS,
            nullable_fields={"amount", "currency"},
        )


def test_null_and_absent_are_distinct():
    value = _proposed_action_fixture(amount=None, currency=None)

    canonical = canonical_json(
        value,
        schema_version=PROPOSED_ACTION_SCHEMA_VERSION,
        allowed_fields=PROPOSED_ACTION_ALLOWED_FIELDS,
        nullable_fields={"amount", "currency"},
    )

    assert '"amount":null' in canonical
    assert '"currency":null' in canonical

    absent = _proposed_action_fixture()
    absent.pop("amount")
    with pytest.raises(CanonicalHashError, match="absent"):
        canonical_json(
            absent,
            schema_version=PROPOSED_ACTION_SCHEMA_VERSION,
            allowed_fields=PROPOSED_ACTION_ALLOWED_FIELDS,
            nullable_fields={"amount", "currency"},
        )


def test_datetime_requires_fixed_millisecond_utc():
    value = {
        "schema_version": "datetime_fixture.v1",
        "created_at": datetime(2026, 6, 15, 0, 0, 0, 123000, tzinfo=UTC),
    }

    assert (
        canonical_json(
            value,
            schema_version="datetime_fixture.v1",
            allowed_fields={"schema_version", "created_at"},
        )
        == '{"created_at":"2026-06-15T00:00:00.123Z","schema_version":"datetime_fixture.v1"}'
    )

    with pytest.raises(CanonicalHashError, match="UTC"):
        canonical_json(
            {
                "schema_version": "datetime_fixture.v1",
                "created_at": datetime(2026, 6, 15, 0, 0, 0),
            },
            schema_version="datetime_fixture.v1",
            allowed_fields={"schema_version", "created_at"},
        )

    with pytest.raises(CanonicalHashError, match="millisecond"):
        canonical_json(
            {
                "schema_version": "datetime_fixture.v1",
                "created_at": datetime(2026, 6, 15, 0, 0, 0, 123456, tzinfo=UTC),
            },
            schema_version="datetime_fixture.v1",
            allowed_fields={"schema_version", "created_at"},
        )


def test_money_requires_string_scale():
    with pytest.raises(CanonicalHashError, match="amount"):
        canonical_json(
            _proposed_action_fixture(amount=100),
            schema_version=PROPOSED_ACTION_SCHEMA_VERSION,
            allowed_fields=PROPOSED_ACTION_ALLOWED_FIELDS,
            nullable_fields={"amount", "currency"},
        )

    with pytest.raises(CanonicalHashError, match="amount"):
        canonical_json(
            _proposed_action_fixture(amount="100.0"),
            schema_version=PROPOSED_ACTION_SCHEMA_VERSION,
            allowed_fields=PROPOSED_ACTION_ALLOWED_FIELDS,
            nullable_fields={"amount", "currency"},
        )
