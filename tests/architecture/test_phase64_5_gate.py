from __future__ import annotations

import ast
import base64
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
import subprocess

import pytest
from pydantic import ValidationError


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _reviewed_root(tmp_path: Path) -> tuple[Path, str, str, str, str]:
    root = tmp_path / "repo"
    from src.repositories.provider_execution_authority_repo import PROTECTED_CODE_PATHS

    for relative in PROTECTED_CODE_PATHS:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("c0\n", encoding="utf-8")
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "gate@example.invalid")
    _git(root, "config", "user.name", "Gate Test")
    _git(root, "add", *PROTECTED_CODE_PATHS)
    _git(root, "commit", "-qm", "c0")
    c0_commit = _git(root, "rev-parse", "HEAD")
    c0_tree = _git(root, "rev-parse", "HEAD^{tree}")
    (root / PROTECTED_CODE_PATHS[2]).write_text("c1\n", encoding="utf-8")
    _git(root, "add", PROTECTED_CODE_PATHS[2])
    _git(root, "commit", "-qm", "c1")
    return root, c0_commit, c0_tree, _git(root, "rev-parse", "HEAD"), _git(root, "rev-parse", "HEAD^{tree}")


def _write_evidence(root: Path, *, kind: str, suffix: str) -> tuple[Path, Path]:
    artifact = root / f"{kind}-{suffix}.md"
    if kind == "code":
        artifact.write_text("---\nstatus: clean\nfindings:\n  total: 0\n---\n# Review\n", encoding="utf-8")
    else:
        artifact.write_text("---\nstatus: verified\nthreats_open: 0\n---\n# Security\n", encoding="utf-8")
    gate = root / f"gate-{suffix}.json"
    gate.write_text(
        json.dumps({"schema_version": "phase64_5.gate_report.v1", "result": "pass"}, sort_keys=True),
        encoding="utf-8",
    )
    return artifact, gate


def _seal_pair(root: Path, *, stage: str, suffix: str, output_root: Path):
    from scripts.check_phase64_5_gate import seal_review_attestation

    paths = []
    for kind, role, invocation in (
        ("code", "gsd-code-reviewer", "$gsd-code-review 64.5 --depth=deep"),
        ("security", "gsd-security-auditor", "$gsd-secure-phase 64.5"),
    ):
        artifact, gate = _write_evidence(root, kind=kind, suffix=f"{suffix}-{kind}")
        paths.append(
            seal_review_attestation(
                stage=stage,
                kind=kind,
                collaboration_canonical_task_name=f"/root/{suffix}_{kind}",
                actual_agent_role=role,
                workflow_invocation=invocation,
                standard_artifact_path=artifact,
                gate_report_path=gate,
                output_root=output_root,
                project_root=root,
                sealed_at=datetime(2026, 8, 13, tzinfo=UTC),
            )
        )
    return tuple(paths)


def test_attestation_seals_real_standard_bytes_and_rejects_fabricated_fields(tmp_path: Path) -> None:
    from scripts.check_phase64_5_gate import (
        GateRefusal,
        ReviewAttestationV1,
        load_review_attestation,
        seal_review_attestation,
    )

    root, _, _, _, _ = _reviewed_root(tmp_path)
    artifact, gate = _write_evidence(root, kind="code", suffix="c1")
    output = root / ".planning"
    path = seal_review_attestation(
        stage="c1",
        kind="code",
        collaboration_canonical_task_name="/root/code_review_c1",
        actual_agent_role="gsd-code-reviewer",
        workflow_invocation="$gsd-code-review 64.5 --depth=deep",
        standard_artifact_path=artifact,
        gate_report_path=gate,
        output_root=output,
        project_root=root,
    )
    loaded = load_review_attestation(path, project_root=root)
    assert loaded.standard_artifact_frontmatter == {"status": "clean", "findings": {"total": 0}}
    assert loaded.standard_artifact_sha256 == "sha256:" + hashlib.sha256(artifact.read_bytes()).hexdigest()
    assert path.name == "64.5-C1-CODE-REVIEW-ATTESTATION.json"
    assert "self_hash" not in path.read_text(encoding="utf-8")

    with pytest.raises(GateRefusal, match="create_only_conflict"):
        seal_review_attestation(
            stage="c1",
            kind="code",
            collaboration_canonical_task_name="/root/code_review_c1",
            actual_agent_role="gsd-code-reviewer",
            workflow_invocation="$gsd-code-review 64.5 --depth=deep",
            standard_artifact_path=artifact,
            gate_report_path=gate,
            output_root=output,
            project_root=root,
        )

    fabricated = loaded.model_dump(mode="json") | {"reviewed_commit": loaded.protected_code_commit}
    with pytest.raises(ValidationError):
        ReviewAttestationV1.model_validate(fabricated)


def test_review_attestations_reject_embedded_hash_role_agent_and_gate_mismatch(tmp_path: Path) -> None:
    from scripts.check_phase64_5_gate import GateRefusal, validate_review_attestations

    root, _, _, _, _ = _reviewed_root(tmp_path)
    output = root / ".planning"
    code_path, security_path = _seal_pair(root, stage="c1", suffix="c1", output_root=output)
    assert (
        len(
            validate_review_attestations(
                (code_path, security_path),
                project_root=root,
                require_stage="c1",
                require_current_protected_base=True,
            )
        )
        == 2
    )

    original = json.loads(security_path.read_bytes())
    cases = (
        {**original, "collaboration_canonical_task_name": "/root/c1_code"},
        {**original, "actual_agent_role": "gsd-code-reviewer"},
        {**original, "standard_artifact_sha256": "sha256:" + "0" * 64},
        {**original, "gate_report_bytes_base64": base64.b64encode(b'{"result":"fail"}').decode("ascii")},
    )
    for index, value in enumerate(cases):
        forged = root / f"forged-{index}.json"
        forged.write_text(json.dumps(value), encoding="utf-8")
        with pytest.raises(GateRefusal):
            validate_review_attestations(
                (code_path, forged),
                project_root=root,
                require_stage="c1",
            )


def test_four_attestations_bind_exact_git_transition_and_promotion_candidate(tmp_path: Path) -> None:
    from scripts.check_phase64_5_gate import (
        GateRefusal,
        build_promotion_request,
        create_promotion_candidate,
        load_promotion_candidate,
        load_review_attestation,
        validate_review_attestations,
    )

    root, c0_commit, c0_tree, c1_commit, c1_tree = _reviewed_root(tmp_path)
    _git(root, "checkout", "-q", c0_commit)
    c0_paths = _seal_pair(root, stage="c0", suffix="c0", output_root=root / ".planning")
    _git(root, "checkout", "-q", c1_commit)
    c1_paths = _seal_pair(root, stage="c1", suffix="c1", output_root=root / ".planning")
    paths = (*c0_paths, *c1_paths)
    loaded = validate_review_attestations(paths, project_root=root)
    candidate_path = create_promotion_candidate(
        c0_code_attestation=c0_paths[0],
        c0_security_attestation=c0_paths[1],
        output_root=root / "candidates",
        project_root=root,
    )
    candidate = load_promotion_candidate(candidate_path, project_root=root)
    assert (candidate.protected_code_c0_commit, candidate.protected_code_c0_tree_hash) == (c0_commit, c0_tree)
    assert (candidate.protected_code_c1_commit, candidate.protected_code_c1_tree_hash) == (c1_commit, c1_tree)
    request = build_promotion_request(
        candidate=candidate,
        attestations=tuple(zip(paths, loaded, strict=True)),
        project_root=root,
    )
    assert request.c0_code_review_artifact_sha256 == loaded[0].standard_artifact_sha256
    assert request.c1_security_artifact_sha256 == loaded[3].standard_artifact_sha256

    forged = candidate.model_copy(update={"protected_code_c1_tree_hash": "0" * 40})
    with pytest.raises(GateRefusal):
        build_promotion_request(
            candidate=forged,
            attestations=tuple((path, load_review_attestation(path, project_root=root)) for path in paths),
            project_root=root,
        )


def test_checker_has_one_named_promotion_mutator_and_other_modes_are_read_only() -> None:
    root = Path(__file__).resolve().parents[2]
    source = (root / "scripts/check_phase64_5_gate.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    mutating_calls = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr == "promote_reviewed_execution":
                scope = next(
                    (
                        parent.name
                        for parent in ast.walk(tree)
                        if isinstance(parent, ast.AsyncFunctionDef) and node in ast.walk(parent)
                    ),
                    "",
                )
                mutating_calls.append(scope)
    assert mutating_calls == ["promote_reviewed_execution"]
    assert 'commands.add_parser("seal-review-attestation")' in source
    assert 'commands.add_parser("review-attestations")' in source
    assert 'commands.add_parser("promotion-candidate")' in source
    assert 'commands.add_parser("promote-reviewed-execution")' in source
    assert "EmbeddingService" not in source
    assert "live_verifier_requires_phase_runtime" not in source
    assert "verify_candidate_live_state" in source
    assert "verify_selected_pass_live_state" in source
