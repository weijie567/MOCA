from __future__ import annotations

import re
from pathlib import Path


COVERAGE_PATH = Path(".planning/phases/16-long-term-case-memory/16-COVERAGE.md")
PHASE16_REQUIREMENTS = {
    "MEMID-01",
    "MEMSCHEMA-01",
    "LONGMEM-01",
    "LONGMEM-02",
    "LONGMEM-03",
    "CASEMEM-01",
    "CASEMEM-02",
    "CASEMEM-03",
    "TOMBSTONE-01",
    "TOMBSTONE-02",
    "MEMCTX-01",
    "MEMCTX-02",
    "MEMREVIEW-01",
    "MEMEVAL-01",
}


def test_phase16_coverage_manifest_lists_all_requirement_ids() -> None:
    assert COVERAGE_PATH.exists(), "Phase 16 coverage manifest must exist before verify-work"

    text = COVERAGE_PATH.read_text(encoding="utf-8")
    listed_ids = set(re.findall(r"\b[A-Z]+-\d{2}\b", text))

    assert PHASE16_REQUIREMENTS <= listed_ids


def test_phase16_coverage_manifest_maps_each_requirement_to_verification() -> None:
    text = COVERAGE_PATH.read_text(encoding="utf-8")

    for requirement_id in PHASE16_REQUIREMENTS:
        row_match = re.search(rf"^\|\s*{requirement_id}\s*\|(?P<row>.+)$", text, re.MULTILINE)
        assert row_match is not None, f"{requirement_id} must have a manifest table row"
        row = row_match.group("row")
        assert "tests/" in row, f"{requirement_id} must name test file(s)"
        assert "pytest" in row or "DB-backed fallback" in row, (
            f"{requirement_id} must name an automated command or explicit fallback"
        )
