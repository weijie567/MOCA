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

from src.rag.provider_execution_authority import PROTECTED_PROVIDER_EXECUTION_GRAPH


PROTECTED_PROVIDER_EXECUTION_ENTRYPOINTS = (
    "scripts/reindex_policies.py",
    "scripts/eval_rag_token_chunk_ab.py",
    "scripts/check_phase64_5_gate.py",
)
# Runtime imports may only be excluded here by exact repository-relative path
# with a durable audit reason. C0 intentionally has no exclusions.
AUDITED_LOCAL_IMPORT_EXCLUSIONS: dict[str, str] = {}
PROTECTED_GRAPH_FIXTURE_PATHS = tuple(
    "src/rag/provider_execution_authority.py" if scope == "src" else scope
    for scope in PROTECTED_PROVIDER_EXECUTION_GRAPH
)


def _local_module_files(root: Path, module_name: str) -> set[Path]:
    parts = tuple(part for part in module_name.split(".") if part)
    if not parts or parts[0] not in {"scripts", "src"}:
        return set()

    resolved: set[Path] = set()
    for length in range(1, len(parts)):
        package_init = root.joinpath(*parts[:length], "__init__.py")
        if package_init.is_file():
            resolved.add(package_init)
    module_file = root.joinpath(*parts).with_suffix(".py")
    package_init = root.joinpath(*parts, "__init__.py")
    if module_file.is_file():
        resolved.add(module_file)
    if package_init.is_file():
        resolved.add(package_init)
    return resolved


def _imported_local_files(root: Path, source_path: Path) -> set[Path]:
    relative = source_path.relative_to(root)
    module_parts = list(relative.with_suffix("").parts)
    package_parts = module_parts if module_parts[-1] == "__init__" else module_parts[:-1]
    if package_parts and package_parts[-1] == "__init__":
        package_parts.pop()

    imported: set[Path] = set()
    for node in ast.walk(ast.parse(source_path.read_text(encoding="utf-8"))):
        module_names: list[str] = []
        if isinstance(node, ast.Import):
            module_names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                keep = len(package_parts) - (node.level - 1)
                if keep < 0:
                    continue
                base_parts = [*package_parts[:keep]]
            else:
                base_parts = []
            if node.module:
                base_parts.extend(node.module.split("."))
            if base_parts:
                module_names.append(".".join(base_parts))
                module_names.extend(".".join((*base_parts, alias.name)) for alias in node.names if alias.name != "*")
        for module_name in module_names:
            imported.update(_local_module_files(root, module_name))
    return imported


def _resolve_local_import_closure(root: Path) -> set[str]:
    pending = [root / relative for relative in PROTECTED_PROVIDER_EXECUTION_ENTRYPOINTS]
    closure: set[Path] = set()
    while pending:
        source_path = pending.pop()
        if source_path in closure:
            continue
        assert source_path.is_file(), source_path.relative_to(root).as_posix()
        closure.add(source_path)
        pending.extend(_imported_local_files(root, source_path) - closure)
    return {path.relative_to(root).as_posix() for path in closure}


def _covered_by_protected_graph(relative: str) -> bool:
    return any(
        relative == scope or relative.startswith(f"{scope.rstrip('/')}/")
        for scope in PROTECTED_PROVIDER_EXECUTION_GRAPH
    )


def test_protected_provider_execution_graph_covers_recursive_local_runtime_imports() -> None:
    root = Path(__file__).resolve().parents[2]
    runtime_closure = _resolve_local_import_closure(root)

    assert not (set(AUDITED_LOCAL_IMPORT_EXCLUSIONS) - runtime_closure)
    assert all(reason.strip() for reason in AUDITED_LOCAL_IMPORT_EXCLUSIONS.values())
    unprotected = sorted(
        relative
        for relative in runtime_closure
        if relative not in AUDITED_LOCAL_IMPORT_EXCLUSIONS and not _covered_by_protected_graph(relative)
    )
    assert unprotected == []
    assert "src" in PROTECTED_PROVIDER_EXECUTION_GRAPH
    assert all(not scope.startswith(("tests/", ".planning/")) for scope in PROTECTED_PROVIDER_EXECUTION_GRAPH)

    for consumer in (
        root / "src/repositories/provider_execution_authority_repo.py",
        root / "scripts/check_phase64_5_gate.py",
    ):
        source = consumer.read_text(encoding="utf-8")
        assert "PROTECTED_PROVIDER_EXECUTION_GRAPH" in source


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _reviewed_root(tmp_path: Path) -> tuple[Path, str, str, str, str]:
    root = tmp_path / "repo"

    for relative in PROTECTED_GRAPH_FIXTURE_PATHS:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("c0\n", encoding="utf-8")
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "gate@example.invalid")
    _git(root, "config", "user.name", "Gate Test")
    _git(root, "add", *PROTECTED_PROVIDER_EXECUTION_GRAPH)
    _git(root, "commit", "-qm", "c0")
    c0_commit = _git(root, "rev-parse", "HEAD")
    c0_tree = _git(root, "rev-parse", "HEAD^{tree}")
    (root / PROTECTED_PROVIDER_EXECUTION_GRAPH[2]).write_text("c1\n", encoding="utf-8")
    _git(root, "add", PROTECTED_PROVIDER_EXECUTION_GRAPH[2])
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
        json.dumps(
            {
                "schema_version": "phase64_5.gate_report.v1",
                "result": "pass",
                "protected_code_commit": _git(root, "rev-parse", "HEAD"),
                "protected_code_tree_hash": _git(root, "rev-parse", "HEAD^{tree}"),
            },
            sort_keys=True,
        ),
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


@pytest.mark.parametrize("dirty_relative", PROTECTED_GRAPH_FIXTURE_PATHS)
@pytest.mark.asyncio
async def test_every_protected_provider_execution_path_refuses_all_promotion_and_dispatch_gates(
    tmp_path: Path,
    dirty_relative: str,
) -> None:
    from scripts.check_phase64_5_gate import (
        GateRefusal,
        create_promotion_candidate,
        seal_review_attestation,
    )
    from src.rag.provider_execution_authority import (
        ProviderExecutionAuthorityError,
        ProviderExecutionAuthorityService,
    )
    from src.repositories.provider_execution_authority_repo import ProviderExecutionAuthorityRepository

    root, c0_commit, _, c1_commit, _ = _reviewed_root(tmp_path)
    _git(root, "checkout", "-q", c0_commit)
    c0_paths = _seal_pair(root, stage="c0", suffix="c0", output_root=root / ".planning")
    _git(root, "checkout", "-q", c1_commit)
    dirty_path = root / dirty_relative
    dirty_path.write_text(dirty_path.read_text(encoding="utf-8") + "dirty\n", encoding="utf-8")

    artifact, gate = _write_evidence(root, kind="code", suffix="dirty-c1")
    with pytest.raises(GateRefusal, match="protected_code_dirty"):
        seal_review_attestation(
            stage="c1",
            kind="code",
            collaboration_canonical_task_name="/root/dirty_code",
            actual_agent_role="gsd-code-reviewer",
            workflow_invocation="$gsd-code-review 64.5 --depth=deep",
            standard_artifact_path=artifact,
            gate_report_path=gate,
            output_root=root / "dirty-attestations",
            project_root=root,
        )
    with pytest.raises(GateRefusal, match="protected_code_dirty"):
        create_promotion_candidate(
            c0_code_attestation=c0_paths[0],
            c0_security_attestation=c0_paths[1],
            output_root=root / "promotion-candidates",
            project_root=root,
        )

    repository = ProviderExecutionAuthorityRepository(None, project_entry=root)  # type: ignore[arg-type]
    with pytest.raises(ProviderExecutionAuthorityError, match="promotion_stale"):
        await repository.inspect_current_code_identity()

    mutations: list[str] = []

    class DirtyRepository:
        async def require_current_promotion(self):
            return await repository.inspect_current_code_identity()

        async def promote_reviewed_execution(self, _request):
            return await repository.inspect_current_code_identity()

        async def issue_authority_root(self, _request):
            mutations.append("issue")

        async def reserve_and_commit(self, _request):
            mutations.append("reserve")

        async def recheck_dispatch(self, _reservation):
            mutations.append("recheck")

    service = ProviderExecutionAuthorityService(DirtyRepository())
    for operation in (
        service.promote_reviewed_execution,
        service.issue_authority_root,
        service.reserve_and_commit,
        service.recheck_dispatch,
    ):
        with pytest.raises(ProviderExecutionAuthorityError, match="promotion_stale"):
            await operation(object())  # type: ignore[arg-type]
    assert mutations == []


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


def test_attestation_binds_gate_reviewed_identity_across_evidence_only_carrier_commit(tmp_path: Path) -> None:
    from scripts.check_phase64_5_gate import seal_review_attestation

    root, _, _, reviewed_commit, reviewed_tree = _reviewed_root(tmp_path)
    artifact, gate = _write_evidence(root, kind="code", suffix="reviewed-c1")
    evidence = root / "evidence-only.md"
    evidence.write_text("review evidence\n", encoding="utf-8")
    _git(root, "add", "evidence-only.md")
    _git(root, "commit", "-qm", "commit review evidence")
    carrier_commit = _git(root, "rev-parse", "HEAD")
    assert carrier_commit != reviewed_commit

    path = seal_review_attestation(
        stage="c1",
        kind="code",
        collaboration_canonical_task_name="/root/reviewed_identity",
        actual_agent_role="gsd-code-reviewer",
        workflow_invocation="$gsd-code-review 64.5 --depth=deep",
        standard_artifact_path=artifact,
        gate_report_path=gate,
        output_root=root / ".planning",
        project_root=root,
    )
    loaded = json.loads(path.read_bytes())
    assert loaded["protected_code_commit"] == reviewed_commit
    assert loaded["protected_code_tree_hash"] == reviewed_tree


def test_attestation_rejects_gate_report_without_reviewed_identity(tmp_path: Path) -> None:
    from scripts.check_phase64_5_gate import GateRefusal, seal_review_attestation

    root, _, _, _, _ = _reviewed_root(tmp_path)
    artifact, gate = _write_evidence(root, kind="code", suffix="missing-identity")
    gate.write_text(
        json.dumps({"schema_version": "phase64_5.gate_report.v1", "result": "pass"}),
        encoding="utf-8",
    )

    with pytest.raises(GateRefusal, match="gate_report_protected_identity_missing"):
        seal_review_attestation(
            stage="c1",
            kind="code",
            collaboration_canonical_task_name="/root/missing_identity",
            actual_agent_role="gsd-code-reviewer",
            workflow_invocation="$gsd-code-review 64.5 --depth=deep",
            standard_artifact_path=artifact,
            gate_report_path=gate,
            output_root=root / ".planning",
            project_root=root,
        )


def test_attestation_frontmatter_canonicalizes_yaml_dates_before_replay(tmp_path: Path) -> None:
    from scripts.check_phase64_5_gate import load_review_attestation, seal_review_attestation

    root, _, _, _, _ = _reviewed_root(tmp_path)
    artifact = root / "dated-review.md"
    artifact.write_text(
        "---\n"
        "status: clean\n"
        "reviewed: 2026-08-13T03:28:29Z\n"
        "created: 2026-08-13\n"
        "findings:\n"
        "  total: 0\n"
        "---\n"
        "# Review\n",
        encoding="utf-8",
    )
    gate = root / "gate-dated.json"
    reviewed_commit = _git(root, "rev-parse", "HEAD")
    reviewed_tree = _git(root, "rev-parse", "HEAD^{tree}")
    gate.write_text(
        json.dumps(
            {
                "schema_version": "phase64_5.gate_report.v1",
                "result": "pass",
                "protected_code_commit": reviewed_commit,
                "protected_code_tree_hash": reviewed_tree,
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    path = seal_review_attestation(
        stage="c0",
        kind="code",
        collaboration_canonical_task_name="/root/dated_review",
        actual_agent_role="gsd-code-reviewer",
        workflow_invocation="$gsd-code-review 64.5 --depth=deep",
        standard_artifact_path=artifact,
        gate_report_path=gate,
        output_root=root / ".planning",
        project_root=root,
        sealed_at=datetime(2026, 8, 13, tzinfo=UTC),
    )

    loaded = load_review_attestation(path, project_root=root)
    assert loaded.standard_artifact_frontmatter["reviewed"] == "2026-08-13T03:28:29+00:00"
    assert loaded.standard_artifact_frontmatter["created"] == "2026-08-13"


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


def test_review_attestations_remain_current_across_evidence_only_commits(tmp_path: Path) -> None:
    from scripts.check_phase64_5_gate import GateRefusal, validate_review_attestations

    root, _, _, _, _ = _reviewed_root(tmp_path)
    output = root / ".planning"
    paths = _seal_pair(root, stage="c0", suffix="c0", output_root=output)
    _git(
        root,
        "add",
        ".planning",
        "code-c0-code.md",
        "security-c0-security.md",
        "gate-c0-code.json",
        "gate-c0-security.json",
    )
    _git(root, "commit", "-qm", "seal reviewed evidence")

    assert (
        len(
            validate_review_attestations(
                paths,
                project_root=root,
                require_stage="c0",
                require_current_protected_base=True,
            )
        )
        == 2
    )

    protected = root / PROTECTED_GRAPH_FIXTURE_PATHS[0]
    protected.write_text(protected.read_text(encoding="utf-8") + "changed\n", encoding="utf-8")
    _git(root, "add", PROTECTED_GRAPH_FIXTURE_PATHS[0])
    _git(root, "commit", "-qm", "change protected runtime")
    with pytest.raises(GateRefusal, match="attestation_not_current"):
        validate_review_attestations(
            paths,
            project_root=root,
            require_stage="c0",
            require_current_protected_base=True,
        )


def test_shared_current_equivalence_detects_protected_race_after_diff(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import src.rag.provider_execution_authority as authority_module
    from src.rag.provider_execution_authority import (
        ProtectedCodeIdentityError,
        require_current_protected_code_equivalence,
    )

    root, _, _, reviewed_commit, reviewed_tree = _reviewed_root(tmp_path)
    original = authority_module._protected_git_bytes
    mutated = False

    def racing_git(project_root: Path, *args: str) -> bytes:
        nonlocal mutated
        result = original(project_root, *args)
        if not mutated and args and args[0] == "diff":
            protected = root / PROTECTED_GRAPH_FIXTURE_PATHS[0]
            protected.write_text(protected.read_text(encoding="utf-8") + "raced\n", encoding="utf-8")
            mutated = True
        return result

    monkeypatch.setattr(authority_module, "_protected_git_bytes", racing_git)
    with pytest.raises(ProtectedCodeIdentityError):
        require_current_protected_code_equivalence(
            root,
            reviewed_commit=reviewed_commit,
            reviewed_tree_hash=reviewed_tree,
        )


def test_same_stage_code_and_security_must_bind_the_exact_same_gate_report(tmp_path: Path) -> None:
    from scripts.check_phase64_5_gate import GateRefusal, validate_review_attestations

    root, _, _, _, _ = _reviewed_root(tmp_path)
    code_path, security_path = _seal_pair(
        root,
        stage="c1",
        suffix="c1-distinct-gate",
        output_root=root / ".planning",
    )
    security = json.loads(security_path.read_bytes())
    distinct_gate_payload = json.loads(base64.b64decode(security["gate_report_bytes_base64"]))
    distinct_gate = json.dumps(distinct_gate_payload | {"evidence": "different"}, sort_keys=True).encode()
    security["gate_report_bytes_base64"] = base64.b64encode(distinct_gate).decode("ascii")
    security["gate_report_sha256"] = "sha256:" + hashlib.sha256(distinct_gate).hexdigest()
    security_path.write_text(json.dumps(security), encoding="utf-8")

    with pytest.raises(GateRefusal, match="attestation_stage_gate_mismatch"):
        validate_review_attestations(
            (code_path, security_path),
            project_root=root,
            require_stage="c1",
        )


def test_candidate_indexes_c0_by_kind_and_rejects_same_commit_replacement(tmp_path: Path) -> None:
    from scripts.check_phase64_5_gate import (
        GateRefusal,
        build_promotion_request,
        create_promotion_candidate,
        load_promotion_candidate,
        load_review_attestation,
        validate_review_attestations,
    )

    root, c0_commit, _, c1_commit, _ = _reviewed_root(tmp_path)
    _git(root, "checkout", "-q", c0_commit)
    original_c0 = _seal_pair(root, stage="c0", suffix="original-c0", output_root=root / "original")
    replacement_c0 = _seal_pair(root, stage="c0", suffix="replacement-c0", output_root=root / "replacement")
    replacement_gate_payload = json.loads(
        base64.b64decode(json.loads(replacement_c0[0].read_bytes())["gate_report_bytes_base64"])
    )
    replacement_gate = json.dumps(replacement_gate_payload | {"evidence": "replacement"}, sort_keys=True).encode()
    for replacement_path in replacement_c0:
        replacement = json.loads(replacement_path.read_bytes())
        replacement_artifact = base64.b64decode(replacement["standard_artifact_bytes_base64"]) + b"\nReplacement\n"
        replacement["standard_artifact_bytes_base64"] = base64.b64encode(replacement_artifact).decode("ascii")
        replacement["standard_artifact_sha256"] = "sha256:" + hashlib.sha256(replacement_artifact).hexdigest()
        replacement["gate_report_bytes_base64"] = base64.b64encode(replacement_gate).decode("ascii")
        replacement["gate_report_sha256"] = "sha256:" + hashlib.sha256(replacement_gate).hexdigest()
        replacement_path.write_text(json.dumps(replacement), encoding="utf-8")
    _git(root, "checkout", "-q", c1_commit)
    c1_paths = _seal_pair(root, stage="c1", suffix="c1", output_root=root / "c1")

    candidate_path = create_promotion_candidate(
        c0_code_attestation=original_c0[1],
        c0_security_attestation=original_c0[0],
        output_root=root / "candidates",
        project_root=root,
    )
    candidate = load_promotion_candidate(candidate_path, project_root=root)
    original_code = load_review_attestation(original_c0[0], project_root=root)
    original_security = load_review_attestation(original_c0[1], project_root=root)
    assert (
        candidate.c0_code_review_attestation_sha256
        == "sha256:" + hashlib.sha256(original_c0[0].read_bytes()).hexdigest()
    )
    assert (
        candidate.c0_security_attestation_sha256 == "sha256:" + hashlib.sha256(original_c0[1].read_bytes()).hexdigest()
    )
    assert candidate.c0_code_review_artifact_sha256 == original_code.standard_artifact_sha256
    assert candidate.c0_security_artifact_sha256 == original_security.standard_artifact_sha256

    replacement_paths = (*replacement_c0, *c1_paths)
    replacement_loaded = validate_review_attestations(replacement_paths, project_root=root)
    replacement_code, replacement_security = replacement_loaded[:2]
    candidate_values = candidate.model_dump(
        mode="python",
        exclude={"schema_version", "candidate_hash"},
    )
    attestation_rebound = type(candidate).seal(
        **(
            candidate_values
            | {
                "c0_code_review_attestation_sha256": "sha256:"
                + hashlib.sha256(replacement_c0[0].read_bytes()).hexdigest(),
                "c0_security_attestation_sha256": "sha256:"
                + hashlib.sha256(replacement_c0[1].read_bytes()).hexdigest(),
            }
        )
    )
    attestation_rebound_values = attestation_rebound.model_dump(
        mode="python",
        exclude={"schema_version", "candidate_hash"},
    )
    artifact_rebound = type(candidate).seal(
        **(
            attestation_rebound_values
            | {
                "c0_code_review_artifact_sha256": replacement_code.standard_artifact_sha256,
                "c0_security_artifact_sha256": replacement_security.standard_artifact_sha256,
            }
        )
    )
    for stale_candidate in (candidate, attestation_rebound, artifact_rebound):
        with pytest.raises(GateRefusal, match="promotion_candidate_attestation_mismatch"):
            build_promotion_request(
                candidate=stale_candidate,
                attestations=tuple(zip(replacement_paths, replacement_loaded, strict=True)),
                project_root=root,
            )


def test_missing_candidate_lookup_is_strictly_noncreating(tmp_path: Path) -> None:
    from scripts.check_phase64_5_gate import GateRefusal, _candidate_from_directory

    root, _, _, _, _ = _reviewed_root(tmp_path)
    missing = root / "read-only" / "missing-candidates"

    with pytest.raises(GateRefusal, match="promotion_candidate_not_unique"):
        _candidate_from_directory(missing, project_root=root)

    assert not (root / "read-only").exists()


def test_symlinked_output_descendant_cannot_create_outside_repository(tmp_path: Path) -> None:
    from scripts.check_phase64_5_gate import GateRefusal, seal_review_attestation

    root, _, _, _, _ = _reviewed_root(tmp_path)
    external = tmp_path / "external"
    external.mkdir()
    linked = root / "linked-output"
    linked.symlink_to(external, target_is_directory=True)
    artifact, gate = _write_evidence(root, kind="code", suffix="nofollow")

    with pytest.raises(GateRefusal, match="output_symlink_forbidden"):
        seal_review_attestation(
            stage="c1",
            kind="code",
            collaboration_canonical_task_name="/root/nofollow_code",
            actual_agent_role="gsd-code-reviewer",
            workflow_invocation="$gsd-code-review 64.5 --depth=deep",
            standard_artifact_path=artifact,
            gate_report_path=gate,
            output_root=linked / "missing" / "attestations",
            project_root=root,
        )

    assert list(external.iterdir()) == []
    assert linked.is_symlink()


def test_output_parent_swap_is_detected_without_publishing_to_replacement(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import scripts.check_phase64_5_gate as gate

    root, _, _, _, _ = _reviewed_root(tmp_path)
    output = root / "race-output"
    output.mkdir()
    detached = root / "detached-output"
    external = tmp_path / "race-external"
    external.mkdir()
    artifact, gate_report = _write_evidence(root, kind="code", suffix="parent-swap")
    write_temporary_file = gate._write_temporary_file

    def swap_after_temporary_write(parent_descriptor: int, *, destination_name: str, payload: bytes) -> str:
        temporary_name = write_temporary_file(
            parent_descriptor,
            destination_name=destination_name,
            payload=payload,
        )
        output.rename(detached)
        output.symlink_to(external, target_is_directory=True)
        return temporary_name

    monkeypatch.setattr(gate, "_write_temporary_file", swap_after_temporary_write)
    with pytest.raises(gate.GateRefusal, match="output_parent_changed"):
        gate.seal_review_attestation(
            stage="c1",
            kind="code",
            collaboration_canonical_task_name="/root/parent_swap_code",
            actual_agent_role="gsd-code-reviewer",
            workflow_invocation="$gsd-code-review 64.5 --depth=deep",
            standard_artifact_path=artifact,
            gate_report_path=gate_report,
            output_root=output,
            project_root=root,
        )

    assert list(external.iterdir()) == []
    assert list(detached.iterdir()) == []
    assert output.is_symlink()


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
    _git(root, "add", ".planning", "candidates", "code-*.md", "security-*.md", "gate-*.json")
    _git(root, "commit", "-qm", "seal promotion evidence")
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
