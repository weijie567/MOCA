from __future__ import annotations


def build_integrity_coverage_matrix() -> dict[str, frozenset[str]]:
    """Return the executable Phase 64.2 requirement-to-test matrix."""

    raise NotImplementedError("Phase 64.2 integrity matrix is not implemented")


def test_phase64_2_matrix_maps_every_locked_requirement() -> None:
    matrix = build_integrity_coverage_matrix()

    assert set(matrix) == {
        *(f"SC-64.2-{index}" for index in range(1, 6)),
        *(f"T64.2-{index:02d}" for index in range(1, 9)),
        *(f"CLAUDE-{index:02d}" for index in range(1, 13)),
        *(f"CLAUDE-R2-{index:02d}" for index in range(1, 5)),
    }
    assert all(test_names for test_names in matrix.values())

