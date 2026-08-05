from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def find_integrity_boundary_violations(relative_path: str, source: str) -> frozenset[str]:
    """Return named Phase 64.2 ownership violations for one Python source."""

    raise NotImplementedError("Phase 64.2 boundary guards are not implemented")


def test_phase64_2_guards_reject_representative_pre_phase_patterns() -> None:
    assert find_integrity_boundary_violations(
        "src/agent/events.py",
        "async def emit(*, evidence_snapshot_refs=None): pass",
    ) == frozenset({"emitter_snapshot_input"})


def test_phase64_2_canonical_owners_pass_boundary_guards() -> None:
    owners = (
        "src/knowledge/evidence_identity.py",
        "src/repositories/evidence_version_repo.py",
        "src/approvals/service.py",
        "src/replay/service.py",
        "src/memory/identity.py",
        "src/memory/case_working_context_lifecycle.py",
        "src/memory/case_precedent.py",
        "src/memory/case_memory.py",
    )

    violations = {
        path: find_integrity_boundary_violations(path, (ROOT / path).read_text(encoding="utf-8"))
        for path in owners
    }

    assert violations == {path: frozenset() for path in owners}
