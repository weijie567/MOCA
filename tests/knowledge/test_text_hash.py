from __future__ import annotations

import re

from src.knowledge.text_hash import evidence_text_hash


def test_nfc_composed_and_decomposed_forms_hash_equal():
    assert evidence_text_hash("é") == evidence_text_hash("e\u0301")


def test_outer_whitespace_is_stripped():
    assert evidence_text_hash("  abc  ") == evidence_text_hash("abc")


def test_internal_newlines_are_unified():
    expected = evidence_text_hash("a\nb")

    assert evidence_text_hash("a\r\nb") == expected
    assert evidence_text_hash("a\rb") == expected


def test_policy_text_is_not_case_folded():
    assert evidence_text_hash("Policy") != evidence_text_hash("policy")


def test_hash_output_format_and_frozen_golden_literal():
    result = evidence_text_hash("退款超时")

    assert re.fullmatch(r"sha256:[0-9a-f]{64}", result)
    assert result == "sha256:14da429414366e3cf6996d34022943fe381b4901065dc785fdc66107402a1427"
