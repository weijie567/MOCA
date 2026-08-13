"""Fail-closed Phase 64.5 review, promotion, and live-state gate entry point."""

from __future__ import annotations

import argparse
import asyncio
import base64
from datetime import UTC, datetime
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
import yaml

from src.rag.provider_execution_authority import (
    ExecutionPromotionRequestV1,
    PROTECTED_PROVIDER_EXECUTION_GRAPH,
    ProviderExecutionAuthorityError,
    ProviderExecutionAuthorityService,
    canonical_json_bytes,
    canonical_sha256,
)
from src.repositories.provider_execution_authority_repo import ProviderExecutionAuthorityRepository


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
PHASE_DIRECTORY = REPOSITORY_ROOT / (
    ".planning/phases/64.5-database-backed-provider-budget-and-token-rollout-completion"
)
REVIEW_ATTESTATION_SCHEMA = "phase64_5.review_attestation.v1"
PROMOTION_CANDIDATE_SCHEMA = "phase64_5.promotion_candidate.v1"
GATE_REPORT_SCHEMA = "phase64_5.gate_report.v1"
_GIT_OBJECT_PATTERN = r"^[0-9a-f]{40}$"
_SHA256_PATTERN = r"^sha256:[0-9a-f]{64}$"
_ATTESTATION_FILENAMES = {
    ("c0", "code"): "64.5-C0-CODE-REVIEW-ATTESTATION.json",
    ("c0", "security"): "64.5-C0-SECURITY-ATTESTATION.json",
    ("c1", "code"): "64.5-C1-CODE-REVIEW-ATTESTATION.json",
    ("c1", "security"): "64.5-C1-SECURITY-ATTESTATION.json",
}
_EXPECTED_AGENT_ROLES = {
    "code": "gsd-code-reviewer",
    "security": "gsd-security-auditor",
}
_EXPECTED_WORKFLOW_PREFIXES = {
    "code": "$gsd-code-review",
    "security": "$gsd-secure-phase",
}


class GateRefusal(RuntimeError):
    """Disclosure-safe gate refusal."""


class _FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ReviewAttestationV1(_FrozenModel):
    """Root-recorded review facts; no self hash or identity claim is present."""

    schema_version: Literal["phase64_5.review_attestation.v1"] = REVIEW_ATTESTATION_SCHEMA
    stage: Literal["c0", "c1"]
    kind: Literal["code", "security"]
    collaboration_canonical_task_name: str = Field(min_length=2, max_length=512)
    actual_agent_role: Literal["gsd-code-reviewer", "gsd-security-auditor"]
    workflow_invocation: str = Field(min_length=2, max_length=1024)
    protected_code_commit: str = Field(pattern=_GIT_OBJECT_PATTERN)
    protected_code_tree_hash: str = Field(pattern=_GIT_OBJECT_PATTERN)
    standard_artifact_path: str = Field(min_length=1, max_length=1024)
    standard_artifact_sha256: str = Field(pattern=_SHA256_PATTERN)
    standard_artifact_bytes_base64: str = Field(min_length=1)
    standard_artifact_frontmatter: dict[str, Any]
    gate_report_path: str = Field(min_length=1, max_length=1024)
    gate_report_sha256: str = Field(pattern=_SHA256_PATTERN)
    gate_report_bytes_base64: str = Field(min_length=1)
    gate_report_result: Literal["pass"]
    sealed_at: datetime

    @model_validator(mode="after")
    def validate_attestation_owned_fields(self) -> ReviewAttestationV1:
        if self.sealed_at.tzinfo is None:
            raise ValueError("attestation_time_invalid")
        if self.actual_agent_role != _EXPECTED_AGENT_ROLES[self.kind]:
            raise ValueError("attestation_agent_role_mismatch")
        if not self.workflow_invocation.strip().startswith(_EXPECTED_WORKFLOW_PREFIXES[self.kind]):
            raise ValueError("attestation_workflow_mismatch")
        if not self.collaboration_canonical_task_name.startswith("/"):
            raise ValueError("attestation_canonical_task_name_invalid")
        return self


class PromotionCandidateV1(_FrozenModel):
    schema_version: Literal["phase64_5.promotion_candidate.v1"] = PROMOTION_CANDIDATE_SCHEMA
    protected_code_c0_commit: str = Field(pattern=_GIT_OBJECT_PATTERN)
    protected_code_c0_tree_hash: str = Field(pattern=_GIT_OBJECT_PATTERN)
    protected_code_c1_commit: str = Field(pattern=_GIT_OBJECT_PATTERN)
    protected_code_c1_tree_hash: str = Field(pattern=_GIT_OBJECT_PATTERN)
    c0_to_c1_diff_hash: str = Field(pattern=_SHA256_PATTERN)
    c0_code_review_attestation_sha256: str = Field(pattern=_SHA256_PATTERN)
    c0_security_attestation_sha256: str = Field(pattern=_SHA256_PATTERN)
    c0_code_review_artifact_sha256: str = Field(pattern=_SHA256_PATTERN)
    c0_security_artifact_sha256: str = Field(pattern=_SHA256_PATTERN)
    c0_gate_report_sha256: str = Field(pattern=_SHA256_PATTERN)
    created_at: datetime
    candidate_hash: str = Field(pattern=_SHA256_PATTERN)

    @classmethod
    def seal(cls, **values: Any) -> PromotionCandidateV1:
        payload = {"schema_version": PROMOTION_CANDIDATE_SCHEMA, **values}
        canonical_payload = cls.model_construct(
            **payload,
            candidate_hash="sha256:" + "0" * 64,
        ).model_dump(mode="json", exclude={"candidate_hash"})
        return cls(**canonical_payload, candidate_hash=canonical_sha256(canonical_payload))

    @model_validator(mode="after")
    def validate_candidate(self) -> PromotionCandidateV1:
        if self.created_at.tzinfo is None:
            raise ValueError("candidate_time_invalid")
        payload = self.model_dump(mode="json", exclude={"candidate_hash"})
        if canonical_sha256(payload) != self.candidate_hash:
            raise ValueError("candidate_hash_mismatch")
        if self.protected_code_c0_commit == self.protected_code_c1_commit:
            raise ValueError("candidate_transition_missing")
        return self


class LiveVerificationIdentityV1(_FrozenModel):
    """Read-only handoff identity; every field is rechecked against PostgreSQL."""

    schema_version: Literal["phase64_5.live_verification.v1"] = "phase64_5.live_verification.v1"
    stage: Literal["issued", "complete", "preflight", "terminal"]
    checked_at: datetime
    promotion_id: UUID
    authority_id: UUID
    tenant_id: UUID
    run_token: UUID
    candidate_id: UUID
    incumbent_id: UUID
    candidate_state: str
    candidate_state_version: int = Field(gt=0)
    reviewed_build_reservation_count: int = Field(ge=0)
    reviewed_build_result_count: int = Field(ge=0)
    canonical_ab_reservation_count: int = Field(ge=0)
    canonical_ab_result_count: int = Field(ge=0)
    selected_result_id: UUID | None = None
    verifier_hash: str = Field(pattern=_SHA256_PATTERN)

    @classmethod
    def seal(cls, **values: Any) -> LiveVerificationIdentityV1:
        payload = {"schema_version": "phase64_5.live_verification.v1", **values}
        canonical_payload = cls.model_construct(
            **payload,
            verifier_hash="sha256:" + "0" * 64,
        ).model_dump(mode="json", exclude={"verifier_hash"})
        return cls(**canonical_payload, verifier_hash=canonical_sha256(canonical_payload))

    @model_validator(mode="after")
    def validate_verifier(self) -> LiveVerificationIdentityV1:
        if self.checked_at.tzinfo is None:
            raise ValueError("live_verifier_time_invalid")
        payload = self.model_dump(mode="json", exclude={"verifier_hash"})
        if canonical_sha256(payload) != self.verifier_hash:
            raise ValueError("live_verifier_hash_mismatch")
        if (self.selected_result_id is not None) != (self.stage == "terminal"):
            raise ValueError("live_verifier_selected_result_invalid")
        return self


def seal_review_attestation(
    *,
    stage: Literal["c0", "c1"],
    kind: Literal["code", "security"],
    collaboration_canonical_task_name: str,
    actual_agent_role: str,
    workflow_invocation: str,
    standard_artifact_path: Path,
    gate_report_path: Path,
    output_root: Path = PHASE_DIRECTORY,
    project_root: Path = REPOSITORY_ROOT,
    sealed_at: datetime | None = None,
) -> Path:
    """Verify current bytes/git identity and create one fixed attestation once."""

    root = project_root.resolve(strict=True)
    artifact_path, artifact_relative = _trusted_existing_path(standard_artifact_path, root=root)
    gate_path, gate_relative = _trusted_existing_path(gate_report_path, root=root)
    if _git_bytes(
        root,
        "status",
        "--porcelain=v1",
        "--untracked-files=all",
        "--",
        *PROTECTED_PROVIDER_EXECUTION_GRAPH,
    ):
        raise GateRefusal("protected_code_dirty")
    commit = _git_text(root, "rev-parse", "HEAD")
    tree_hash = _git_text(root, "rev-parse", "HEAD^{tree}")
    artifact_bytes = artifact_path.read_bytes()
    frontmatter = _parse_frontmatter(artifact_bytes)
    _require_standard_artifact(kind=kind, frontmatter=frontmatter)
    gate_bytes = gate_path.read_bytes()
    _require_clean_gate_report(gate_bytes)
    try:
        attestation = ReviewAttestationV1(
            stage=stage,
            kind=kind,
            collaboration_canonical_task_name=collaboration_canonical_task_name,
            actual_agent_role=actual_agent_role,
            workflow_invocation=workflow_invocation,
            protected_code_commit=commit,
            protected_code_tree_hash=tree_hash,
            standard_artifact_path=artifact_relative,
            standard_artifact_sha256=canonical_sha256(artifact_bytes),
            standard_artifact_bytes_base64=base64.b64encode(artifact_bytes).decode("ascii"),
            standard_artifact_frontmatter=frontmatter,
            gate_report_path=gate_relative,
            gate_report_sha256=canonical_sha256(gate_bytes),
            gate_report_bytes_base64=base64.b64encode(gate_bytes).decode("ascii"),
            gate_report_result="pass",
            sealed_at=(sealed_at or datetime.now(UTC)),
        )
    except ValidationError as exc:
        raise GateRefusal("attestation_input_invalid") from exc
    destination = _trusted_output_path(output_root / _ATTESTATION_FILENAMES[(stage, kind)], root=root)
    _write_create_only(
        destination,
        canonical_json_bytes(attestation.model_dump(mode="json")) + b"\n",
        root=root,
    )
    return destination


def load_review_attestation(path: Path, *, project_root: Path = REPOSITORY_ROOT) -> ReviewAttestationV1:
    """Strict-load and independently revalidate all embedded evidence."""

    root = project_root.resolve(strict=True)
    attestation_path, _ = _trusted_existing_path(path, root=root)
    try:
        raw = json.loads(attestation_path.read_bytes())
        attestation = ReviewAttestationV1.model_validate(raw)
        artifact_bytes = base64.b64decode(attestation.standard_artifact_bytes_base64, validate=True)
        gate_bytes = base64.b64decode(attestation.gate_report_bytes_base64, validate=True)
    except (OSError, ValueError, ValidationError) as exc:
        raise GateRefusal("attestation_invalid") from exc
    if (
        canonical_sha256(artifact_bytes) != attestation.standard_artifact_sha256
        or canonical_sha256(gate_bytes) != attestation.gate_report_sha256
    ):
        raise GateRefusal("attestation_embedded_hash_mismatch")
    frontmatter = _parse_frontmatter(artifact_bytes)
    if frontmatter != attestation.standard_artifact_frontmatter:
        raise GateRefusal("attestation_frontmatter_mismatch")
    _require_standard_artifact(kind=attestation.kind, frontmatter=frontmatter)
    _require_clean_gate_report(gate_bytes)
    _require_git_identity(
        root,
        commit=attestation.protected_code_commit,
        tree_hash=attestation.protected_code_tree_hash,
    )
    return attestation


def validate_review_attestations(
    paths: tuple[Path, ...],
    *,
    project_root: Path = REPOSITORY_ROOT,
    require_stage: Literal["c0", "c1"] | None = None,
    require_current_protected_base: bool = False,
) -> tuple[ReviewAttestationV1, ...]:
    if len(paths) not in {2, 4}:
        raise GateRefusal("attestation_set_cardinality_invalid")
    attestations = tuple(load_review_attestation(path, project_root=project_root) for path in paths)
    if len({item.collaboration_canonical_task_name for item in attestations}) != len(attestations):
        raise GateRefusal("attestation_agent_not_distinct")
    combos = {(item.stage, item.kind) for item in attestations}
    expected = (
        {(require_stage, "code"), (require_stage, "security")}
        if require_stage is not None
        else {("c0", "code"), ("c0", "security"), ("c1", "code"), ("c1", "security")}
    )
    if combos != expected:
        raise GateRefusal("attestation_role_stage_set_invalid")
    for stage in {item.stage for item in attestations}:
        stage_items = [item for item in attestations if item.stage == stage]
        if len({(item.protected_code_commit, item.protected_code_tree_hash) for item in stage_items}) != 1:
            raise GateRefusal("attestation_stage_git_mismatch")
        if len({item.gate_report_sha256 for item in stage_items}) != 1:
            raise GateRefusal("attestation_stage_gate_mismatch")
    if len(attestations) == 4:
        c0 = next(item for item in attestations if item.stage == "c0")
        c1 = next(item for item in attestations if item.stage == "c1")
        _require_transition(
            project_root.resolve(strict=True),
            c0_commit=c0.protected_code_commit,
            c0_tree=c0.protected_code_tree_hash,
            c1_commit=c1.protected_code_commit,
            c1_tree=c1.protected_code_tree_hash,
        )
    if require_current_protected_base:
        root = project_root.resolve(strict=True)
        if _git_bytes(
            root,
            "status",
            "--porcelain=v1",
            "--untracked-files=all",
            "--",
            *PROTECTED_PROVIDER_EXECUTION_GRAPH,
        ):
            raise GateRefusal("protected_code_dirty")
        current = (_git_text(root, "rev-parse", "HEAD"), _git_text(root, "rev-parse", "HEAD^{tree}"))
        if any((item.protected_code_commit, item.protected_code_tree_hash) != current for item in attestations):
            raise GateRefusal("attestation_not_current")
    return attestations


def create_promotion_candidate(
    *,
    c0_code_attestation: Path,
    c0_security_attestation: Path,
    output_root: Path,
    project_root: Path = REPOSITORY_ROOT,
    created_at: datetime | None = None,
) -> Path:
    root = project_root.resolve(strict=True)
    c0_paths = (c0_code_attestation, c0_security_attestation)
    validated = validate_review_attestations(
        c0_paths,
        project_root=root,
        require_stage="c0",
    )
    indexed = {(item.stage, item.kind): (path, item) for path, item in zip(c0_paths, validated, strict=True)}
    code_path, code = indexed[("c0", "code")]
    security_path, security = indexed[("c0", "security")]
    if _git_bytes(
        root,
        "status",
        "--porcelain=v1",
        "--untracked-files=all",
        "--",
        *PROTECTED_PROVIDER_EXECUTION_GRAPH,
    ):
        raise GateRefusal("protected_code_dirty")
    c1_commit = _git_text(root, "rev-parse", "HEAD")
    c1_tree = _git_text(root, "rev-parse", "HEAD^{tree}")
    diff_hash = _require_transition(
        root,
        c0_commit=code.protected_code_commit,
        c0_tree=code.protected_code_tree_hash,
        c1_commit=c1_commit,
        c1_tree=c1_tree,
    )
    candidate = PromotionCandidateV1.seal(
        protected_code_c0_commit=code.protected_code_commit,
        protected_code_c0_tree_hash=code.protected_code_tree_hash,
        protected_code_c1_commit=c1_commit,
        protected_code_c1_tree_hash=c1_tree,
        c0_to_c1_diff_hash=diff_hash,
        c0_code_review_attestation_sha256=_path_sha256(code_path),
        c0_security_attestation_sha256=_path_sha256(security_path),
        c0_code_review_artifact_sha256=code.standard_artifact_sha256,
        c0_security_artifact_sha256=security.standard_artifact_sha256,
        c0_gate_report_sha256=code.gate_report_sha256,
        created_at=created_at or datetime.now(UTC),
    )
    destination = _trusted_output_path(output_root / f"{c1_commit}.json", root=root)
    _write_create_only(
        destination,
        canonical_json_bytes(candidate.model_dump(mode="json")) + b"\n",
        root=root,
    )
    return destination


def load_promotion_candidate(path: Path, *, project_root: Path = REPOSITORY_ROOT) -> PromotionCandidateV1:
    candidate_path, _ = _trusted_existing_path(path, root=project_root.resolve(strict=True))
    try:
        return PromotionCandidateV1.model_validate_json(candidate_path.read_bytes())
    except (OSError, ValidationError) as exc:
        raise GateRefusal("promotion_candidate_invalid") from exc


def build_promotion_request(
    *,
    candidate: PromotionCandidateV1,
    attestations: tuple[tuple[Path, ReviewAttestationV1], ...],
    project_root: Path = REPOSITORY_ROOT,
) -> ExecutionPromotionRequestV1:
    root = project_root.resolve(strict=True)
    if len(attestations) != 4:
        raise GateRefusal("promotion_attestation_set_invalid")
    indexed = {(item.stage, item.kind): (path, item) for path, item in attestations}
    if set(indexed) != {("c0", "code"), ("c0", "security"), ("c1", "code"), ("c1", "security")}:
        raise GateRefusal("promotion_attestation_set_invalid")
    c0_code = indexed[("c0", "code")]
    c0_security = indexed[("c0", "security")]
    c1_code = indexed[("c1", "code")]
    c1_security = indexed[("c1", "security")]
    if (
        candidate.protected_code_c0_commit != c0_code[1].protected_code_commit
        or candidate.protected_code_c0_tree_hash != c0_code[1].protected_code_tree_hash
        or candidate.protected_code_c1_commit != c1_code[1].protected_code_commit
        or candidate.protected_code_c1_tree_hash != c1_code[1].protected_code_tree_hash
        or (c0_security[1].protected_code_commit, c0_security[1].protected_code_tree_hash)
        != (c0_code[1].protected_code_commit, c0_code[1].protected_code_tree_hash)
        or (c1_security[1].protected_code_commit, c1_security[1].protected_code_tree_hash)
        != (c1_code[1].protected_code_commit, c1_code[1].protected_code_tree_hash)
        or c0_security[1].gate_report_sha256 != c0_code[1].gate_report_sha256
        or c1_security[1].gate_report_sha256 != c1_code[1].gate_report_sha256
        or candidate.c0_code_review_attestation_sha256 != _path_sha256(c0_code[0])
        or candidate.c0_security_attestation_sha256 != _path_sha256(c0_security[0])
        or candidate.c0_code_review_artifact_sha256 != c0_code[1].standard_artifact_sha256
        or candidate.c0_security_artifact_sha256 != c0_security[1].standard_artifact_sha256
        or candidate.c0_gate_report_sha256 != c0_code[1].gate_report_sha256
    ):
        raise GateRefusal("promotion_candidate_attestation_mismatch")
    actual_diff = _require_transition(
        root,
        c0_commit=candidate.protected_code_c0_commit,
        c0_tree=candidate.protected_code_c0_tree_hash,
        c1_commit=candidate.protected_code_c1_commit,
        c1_tree=candidate.protected_code_c1_tree_hash,
    )
    if actual_diff != candidate.c0_to_c1_diff_hash:
        raise GateRefusal("promotion_candidate_diff_mismatch")
    current = (_git_text(root, "rev-parse", "HEAD"), _git_text(root, "rev-parse", "HEAD^{tree}"))
    if current != (candidate.protected_code_c1_commit, candidate.protected_code_c1_tree_hash):
        raise GateRefusal("promotion_candidate_not_current")
    return ExecutionPromotionRequestV1.seal(
        protected_code_c0_commit=candidate.protected_code_c0_commit,
        protected_code_c0_tree_hash=candidate.protected_code_c0_tree_hash,
        protected_code_c1_commit=candidate.protected_code_c1_commit,
        protected_code_c1_tree_hash=candidate.protected_code_c1_tree_hash,
        c0_to_c1_diff_hash=candidate.c0_to_c1_diff_hash,
        c0_code_review_artifact_sha256=c0_code[1].standard_artifact_sha256,
        c0_security_artifact_sha256=c0_security[1].standard_artifact_sha256,
        c1_code_review_artifact_sha256=c1_code[1].standard_artifact_sha256,
        c1_security_artifact_sha256=c1_security[1].standard_artifact_sha256,
        c0_code_review_attestation_sha256=_path_sha256(c0_code[0]),
        c0_security_attestation_sha256=_path_sha256(c0_security[0]),
        c1_code_review_attestation_sha256=_path_sha256(c1_code[0]),
        c1_security_attestation_sha256=_path_sha256(c1_security[0]),
        c0_gate_report_sha256=c0_code[1].gate_report_sha256,
        c1_gate_report_sha256=c1_code[1].gate_report_sha256,
    )


async def promote_reviewed_execution(
    request: ExecutionPromotionRequestV1,
    *,
    projection_root: Path,
    authority_service: ProviderExecutionAuthorityService | None = None,
) -> Path:
    """The sole checker operation allowed to mutate promotion state."""

    if authority_service is None:
        from src.db.session import SessionLocal

        authority_service = ProviderExecutionAuthorityService(
            ProviderExecutionAuthorityRepository(SessionLocal, project_entry=Path(__file__))
        )
    promoted = await authority_service.promote_reviewed_execution(request)
    readback = await authority_service.require_current_promotion()
    if promoted != readback:
        raise GateRefusal("promotion_readback_mismatch")
    destination = _trusted_output_path(projection_root / f"{promoted.promotion_id}.json", root=REPOSITORY_ROOT)
    _write_create_only(
        destination,
        canonical_json_bytes(promoted.model_dump(mode="json")) + b"\n",
        root=REPOSITORY_ROOT,
    )
    return destination


async def verify_candidate_live_state(
    args: argparse.Namespace,
    *,
    service: ProviderExecutionAuthorityService,
    repository: ProviderExecutionAuthorityRepository,
) -> dict[str, Any]:
    """Read the one shared root and its candidate without changing DB state."""

    return await _verify_live_state(
        args,
        service=service,
        repository=repository,
        selected_pass=False,
    )


async def verify_selected_pass_live_state(
    args: argparse.Namespace,
    *,
    service: ProviderExecutionAuthorityService,
    repository: ProviderExecutionAuthorityRepository,
) -> dict[str, Any]:
    """Read the shared root and its canonical A/B lineage without DB writes."""

    return await _verify_live_state(
        args,
        service=service,
        repository=repository,
        selected_pass=True,
    )


async def _verify_live_state(
    args: argparse.Namespace,
    *,
    service: ProviderExecutionAuthorityService,
    repository: ProviderExecutionAuthorityRepository,
    selected_pass: bool,
) -> dict[str, Any]:
    """Strict read-only wrapper over the existing authoritative repository graph."""

    await service.require_current_promotion()
    if args.identity_file is None:
        raise GateRefusal("live_identity_required")
    try:
        prior = LiveVerificationIdentityV1.model_validate_json(args.identity_file.read_bytes())
    except (OSError, ValidationError) as exc:
        raise GateRefusal("live_identity_invalid") from exc
    projection = await repository.read_projection(authority_id=prior.authority_id)
    if (
        projection.promotion.promotion_id != prior.promotion_id
        or projection.authority.tenant_id != prior.tenant_id
        or projection.authority.run_token != prior.run_token
        or projection.authority.candidate_id != prior.candidate_id
        or projection.authority.source_active_corpus_version_id != prior.incumbent_id
    ):
        raise GateRefusal("live_identity_mismatch")
    canonical = tuple(item for item in projection.reservations if item.purpose.value == "canonical_ab")
    results_by_reservation = {item.reservation_id: item for item in projection.results}
    selected = tuple(
        results_by_reservation[item.reservation_id]
        for item in canonical
        if item.reservation_id in results_by_reservation
        and results_by_reservation[item.reservation_id].result_json.get("outcome") == "selected_pass"
    )
    if args.expect_no_ab_reservation and canonical:
        raise GateRefusal("canonical_ab_reservation_unexpected")
    if args.require_selected_pass and len(selected) != 1:
        raise GateRefusal("selected_pass_required")
    stage = args.stage
    checked = LiveVerificationIdentityV1.seal(
        stage=stage,
        checked_at=datetime.now(UTC),
        promotion_id=projection.promotion.promotion_id,
        authority_id=projection.authority.authority_id,
        tenant_id=projection.authority.tenant_id,
        run_token=projection.authority.run_token,
        candidate_id=projection.authority.candidate_id,
        incumbent_id=projection.authority.source_active_corpus_version_id,
        candidate_state=prior.candidate_state,
        candidate_state_version=prior.candidate_state_version,
        reviewed_build_reservation_count=sum(
            item.purpose.value == "reviewed_build" for item in projection.reservations
        ),
        reviewed_build_result_count=sum(
            item.reservation_id in results_by_reservation
            for item in projection.reservations
            if item.purpose.value == "reviewed_build"
        ),
        canonical_ab_reservation_count=len(canonical),
        canonical_ab_result_count=sum(item.reservation_id in results_by_reservation for item in canonical),
        selected_result_id=selected[0].result_id if selected_pass and selected else None,
    )
    output = _trusted_output_path(args.output, root=REPOSITORY_ROOT)
    _replace_bytes(
        output,
        canonical_json_bytes(checked.model_dump(mode="json")) + b"\n",
        root=REPOSITORY_ROOT,
    )
    return {"result": "pass", "output": output.relative_to(REPOSITORY_ROOT).as_posix()}


def _parse_frontmatter(payload: bytes) -> dict[str, Any]:
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise GateRefusal("standard_artifact_not_utf8") from exc
    lines = text.splitlines()
    if not lines or lines[0] != "---":
        raise GateRefusal("standard_artifact_frontmatter_missing")
    try:
        closing = lines.index("---", 1)
    except ValueError as exc:
        raise GateRefusal("standard_artifact_frontmatter_unclosed") from exc
    try:
        parsed = yaml.load("\n".join(lines[1:closing]), Loader=_UniqueKeyLoader)
    except yaml.YAMLError as exc:
        raise GateRefusal("standard_artifact_frontmatter_invalid") from exc
    if not isinstance(parsed, dict):
        raise GateRefusal("standard_artifact_frontmatter_invalid")
    return parsed


class _UniqueKeyLoader(yaml.SafeLoader):
    pass


def _construct_unique_mapping(loader: _UniqueKeyLoader, node: yaml.MappingNode, deep: bool = False) -> dict[Any, Any]:
    result: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in result:
            raise yaml.constructor.ConstructorError(None, None, "duplicate frontmatter key", key_node.start_mark)
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


_UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_unique_mapping,
)


def _require_standard_artifact(*, kind: str, frontmatter: dict[str, Any]) -> None:
    if kind == "code":
        if frontmatter.get("status") != "clean":
            raise GateRefusal("code_review_not_clean")
    elif type(frontmatter.get("threats_open")) is not int or frontmatter["threats_open"] != 0:
        raise GateRefusal("security_review_has_open_threats")


def _require_clean_gate_report(payload: bytes) -> dict[str, Any]:
    try:
        value = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise GateRefusal("gate_report_invalid") from exc
    if (
        not isinstance(value, dict)
        or value.get("schema_version") != GATE_REPORT_SCHEMA
        or value.get("result") != "pass"
    ):
        raise GateRefusal("gate_report_not_clean")
    return value


def _require_git_identity(root: Path, *, commit: str, tree_hash: str) -> None:
    try:
        actual_tree = _git_text(root, "rev-parse", f"{commit}^{{tree}}")
    except GateRefusal as exc:
        raise GateRefusal("attestation_git_identity_missing") from exc
    if actual_tree != tree_hash:
        raise GateRefusal("attestation_git_tree_mismatch")


def _require_transition(
    root: Path,
    *,
    c0_commit: str,
    c0_tree: str,
    c1_commit: str,
    c1_tree: str,
) -> str:
    _require_git_identity(root, commit=c0_commit, tree_hash=c0_tree)
    _require_git_identity(root, commit=c1_commit, tree_hash=c1_tree)
    if c0_commit == c1_commit:
        raise GateRefusal("protected_transition_missing")
    try:
        _git_bytes(root, "merge-base", "--is-ancestor", c0_commit, c1_commit)
    except GateRefusal as exc:
        raise GateRefusal("protected_transition_not_ancestral") from exc
    diff = _git_bytes(
        root,
        "diff",
        "--binary",
        "--full-index",
        c0_commit,
        c1_commit,
        "--",
        *PROTECTED_PROVIDER_EXECUTION_GRAPH,
    )
    return canonical_sha256(diff)


def _trusted_existing_path(path: Path, *, root: Path) -> tuple[Path, str]:
    candidate = path if path.is_absolute() else root / path
    try:
        resolved = candidate.resolve(strict=True)
        relative = resolved.relative_to(root)
    except (OSError, ValueError) as exc:
        raise GateRefusal("path_outside_repository") from exc
    if not resolved.is_file() or resolved.is_symlink():
        raise GateRefusal("trusted_file_invalid")
    return resolved, relative.as_posix()


def _trusted_output_path(path: Path, *, root: Path) -> Path:
    candidate = path if path.is_absolute() else root / path
    candidate = Path(os.path.abspath(candidate))
    try:
        relative = candidate.relative_to(root)
    except ValueError as exc:
        raise GateRefusal("output_outside_repository") from exc
    if not relative.parts or candidate.name in {"", ".", ".."}:
        raise GateRefusal("output_path_invalid")
    return candidate


def _trusted_existing_directory(path: Path, *, root: Path) -> Path:
    candidate = path if path.is_absolute() else root / path
    candidate = Path(os.path.abspath(candidate))
    try:
        relative = candidate.relative_to(root)
    except ValueError as exc:
        raise GateRefusal("path_outside_repository") from exc
    current = root
    for part in relative.parts:
        current /= part
        try:
            metadata = current.lstat()
        except FileNotFoundError as exc:
            raise GateRefusal("trusted_directory_missing") from exc
        except OSError as exc:
            raise GateRefusal("trusted_directory_invalid") from exc
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
            raise GateRefusal("trusted_directory_invalid")
    return candidate


def _directory_identity(descriptor: int) -> tuple[int, int]:
    metadata = os.fstat(descriptor)
    return metadata.st_dev, metadata.st_ino


def _open_output_component(parent_descriptor: int, part: str) -> int:
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    while True:
        try:
            return os.open(part, flags, dir_fd=parent_descriptor)
        except FileNotFoundError:
            try:
                os.mkdir(part, mode=0o755, dir_fd=parent_descriptor)
                os.fsync(parent_descriptor)
            except FileExistsError:
                continue
            except OSError as exc:
                raise GateRefusal("output_directory_invalid") from exc
        except OSError as exc:
            try:
                metadata = os.stat(part, dir_fd=parent_descriptor, follow_symlinks=False)
            except OSError:
                raise GateRefusal("output_directory_invalid") from exc
            if stat.S_ISLNK(metadata.st_mode):
                raise GateRefusal("output_symlink_forbidden") from exc
            raise GateRefusal("output_directory_invalid") from exc


def _open_pinned_output_parent(
    path: Path,
    *,
    root: Path,
) -> tuple[int, int, str, tuple[str, ...], tuple[tuple[int, int], ...]]:
    destination = _trusted_output_path(path, root=root)
    parent_parts = destination.relative_to(root).parts[:-1]
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    root_descriptor: int | None = None
    try:
        root_descriptor = os.open(root, flags)
        parent_descriptor = os.dup(root_descriptor)
    except OSError as exc:
        if root_descriptor is not None:
            os.close(root_descriptor)
        raise GateRefusal("output_root_invalid") from exc
    identities = [_directory_identity(root_descriptor)]
    try:
        for part in parent_parts:
            next_descriptor = _open_output_component(parent_descriptor, part)
            os.close(parent_descriptor)
            parent_descriptor = next_descriptor
            identities.append(_directory_identity(parent_descriptor))
    except BaseException:
        os.close(parent_descriptor)
        os.close(root_descriptor)
        raise
    return root_descriptor, parent_descriptor, destination.name, parent_parts, tuple(identities)


def _pinned_output_parent_is_current(
    *,
    root: Path,
    parent_parts: tuple[str, ...],
    identities: tuple[tuple[int, int], ...],
) -> bool:
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    descriptors: list[int] = []
    try:
        current = os.open(root, flags)
        descriptors.append(current)
        if _directory_identity(current) != identities[0]:
            return False
        for index, part in enumerate(parent_parts, start=1):
            current = os.open(part, flags, dir_fd=current)
            descriptors.append(current)
            if _directory_identity(current) != identities[index]:
                return False
        return True
    except OSError:
        return False
    finally:
        for descriptor in reversed(descriptors):
            os.close(descriptor)


def _write_temporary_file(parent_descriptor: int, *, destination_name: str, payload: bytes) -> str:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
    for _ in range(32):
        temporary_name = f".{destination_name}.{uuid4().hex}.tmp"
        try:
            descriptor = os.open(temporary_name, flags, 0o600, dir_fd=parent_descriptor)
        except FileExistsError:
            continue
        except OSError as exc:
            raise GateRefusal("output_write_failed") from exc
        descriptor_open = True
        try:
            with os.fdopen(descriptor, "wb", closefd=True) as handle:
                descriptor_open = False
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
        except BaseException:
            if descriptor_open:
                os.close(descriptor)
            try:
                os.unlink(temporary_name, dir_fd=parent_descriptor)
            except OSError:
                pass
            raise
        return temporary_name
    raise GateRefusal("output_temporary_conflict")


def _replace_bytes(path: Path, payload: bytes, *, root: Path) -> None:
    root_descriptor, parent_descriptor, destination_name, parent_parts, identities = _open_pinned_output_parent(
        path,
        root=root,
    )
    temporary_name: str | None = None
    try:
        try:
            destination_metadata = os.stat(destination_name, dir_fd=parent_descriptor, follow_symlinks=False)
        except FileNotFoundError:
            destination_metadata = None
        except OSError as exc:
            raise GateRefusal("output_path_invalid") from exc
        if destination_metadata is not None and stat.S_ISLNK(destination_metadata.st_mode):
            raise GateRefusal("output_symlink_forbidden")
        temporary_name = _write_temporary_file(
            parent_descriptor,
            destination_name=destination_name,
            payload=payload,
        )
        if not _pinned_output_parent_is_current(
            root=root,
            parent_parts=parent_parts,
            identities=identities,
        ):
            raise GateRefusal("output_parent_changed")
        try:
            os.replace(
                temporary_name,
                destination_name,
                src_dir_fd=parent_descriptor,
                dst_dir_fd=parent_descriptor,
            )
        except OSError as exc:
            raise GateRefusal("output_write_failed") from exc
        temporary_name = None
        os.fsync(parent_descriptor)
        if not _pinned_output_parent_is_current(
            root=root,
            parent_parts=parent_parts,
            identities=identities,
        ):
            raise GateRefusal("output_parent_changed")
    finally:
        if temporary_name is not None:
            try:
                os.unlink(temporary_name, dir_fd=parent_descriptor)
            except OSError:
                pass
        os.close(parent_descriptor)
        os.close(root_descriptor)


def _write_create_only(path: Path, payload: bytes, *, root: Path) -> None:
    root_descriptor, parent_descriptor, destination_name, parent_parts, identities = _open_pinned_output_parent(
        path,
        root=root,
    )
    temporary_name: str | None = None
    try:
        temporary_name = _write_temporary_file(
            parent_descriptor,
            destination_name=destination_name,
            payload=payload,
        )
        if not _pinned_output_parent_is_current(
            root=root,
            parent_parts=parent_parts,
            identities=identities,
        ):
            raise GateRefusal("output_parent_changed")
        try:
            os.link(
                temporary_name,
                destination_name,
                src_dir_fd=parent_descriptor,
                dst_dir_fd=parent_descriptor,
                follow_symlinks=False,
            )
        except FileExistsError as exc:
            raise GateRefusal("create_only_conflict") from exc
        except OSError as exc:
            raise GateRefusal("output_write_failed") from exc
        os.fsync(parent_descriptor)
        if not _pinned_output_parent_is_current(
            root=root,
            parent_parts=parent_parts,
            identities=identities,
        ):
            try:
                os.unlink(destination_name, dir_fd=parent_descriptor)
                os.fsync(parent_descriptor)
            except OSError:
                pass
            raise GateRefusal("output_parent_changed")
    finally:
        if temporary_name is not None:
            try:
                os.unlink(temporary_name, dir_fd=parent_descriptor)
            except OSError:
                pass
        os.close(parent_descriptor)
        os.close(root_descriptor)


def _path_sha256(path: Path) -> str:
    try:
        return canonical_sha256(path.read_bytes())
    except OSError as exc:
        raise GateRefusal("evidence_file_unavailable") from exc


def _git_bytes(root: Path, *args: str) -> bytes:
    try:
        return subprocess.run(
            ["git", "-C", str(root), *args],
            check=True,
            capture_output=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError) as exc:
        raise GateRefusal("git_identity_invalid") from exc


def _git_text(root: Path, *args: str) -> str:
    return _git_bytes(root, *args).decode("ascii").strip()


def _candidate_from_directory(directory: Path, *, project_root: Path) -> tuple[Path, PromotionCandidateV1]:
    try:
        root = _trusted_existing_directory(directory, root=project_root.resolve(strict=True))
        candidates = sorted(path for path in root.glob("*.json") if not path.is_symlink() and path.is_file())
    except GateRefusal as exc:
        if str(exc) == "trusted_directory_missing":
            raise GateRefusal("promotion_candidate_not_unique") from None
        raise
    except OSError:
        raise GateRefusal("promotion_candidate_not_unique") from None
    if len(candidates) != 1:
        raise GateRefusal("promotion_candidate_not_unique")
    return candidates[0], load_promotion_candidate(candidates[0], project_root=project_root)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    seal = commands.add_parser("seal-review-attestation")
    seal.add_argument("--stage", choices=("c0", "c1"), required=True)
    seal.add_argument("--kind", choices=("code", "security"), required=True)
    seal.add_argument("--collaboration-canonical-task-name", required=True)
    seal.add_argument("--actual-agent-role", required=True)
    seal.add_argument("--workflow-invocation", required=True)
    seal.add_argument("--standard-artifact", type=Path, required=True)
    seal.add_argument("--gate-report", type=Path, required=True)
    seal.add_argument("--output-root", type=Path, default=PHASE_DIRECTORY)

    reviews = commands.add_parser("review-attestations")
    reviews.add_argument("--code-attestation", type=Path, required=True)
    reviews.add_argument("--security-attestation", type=Path, required=True)
    reviews.add_argument("--require-stage", choices=("c0", "c1"), required=True)
    reviews.add_argument("--require-current-protected-base", action="store_true")

    candidate = commands.add_parser("promotion-candidate")
    candidate.add_argument("--c0-code-attestation", type=Path, required=True)
    candidate.add_argument("--c0-security-attestation", type=Path, required=True)
    candidate.add_argument("--infer-current-protected-commit", action="store_true", required=True)
    candidate.add_argument("--output-root", type=Path, required=True)

    promote = commands.add_parser("promote-reviewed-execution")
    promote.add_argument("--infer-unique-candidate-from", type=Path, required=True)
    for name in ("c0-code", "c0-security", "c1-code", "c1-security"):
        promote.add_argument(f"--{name}-attestation", type=Path, required=True)
    promote.add_argument("--infer-current-protected-commit", action="store_true", required=True)
    promote.add_argument("--projection-root", type=Path, required=True)

    status = commands.add_parser("promotion-status")
    status.add_argument("--require-absent", action="store_true")
    status.add_argument("--require-current", action="store_true")
    status.add_argument("--infer-unique-candidate-from", type=Path)

    for mode in ("candidate", "selected-pass"):
        live = commands.add_parser(mode)
        live.add_argument("--stage", required=True)
        live.add_argument("--identity-file", type=Path)
        live.add_argument("--infer-unique-phase-run", action="store_true")
        live.add_argument("--require-current-promotion", action="store_true")
        live.add_argument("--expect-no-ab-reservation", action="store_true")
        live.add_argument("--require-selected-pass", action="store_true")
        live.add_argument("--output", type=Path, required=True)
    return parser


async def _run_db_command(args: argparse.Namespace) -> dict[str, Any]:
    from sqlalchemy import func, select

    from src.db.models import ProviderExecutionPromotion
    from src.db.session import SessionLocal

    repository = ProviderExecutionAuthorityRepository(SessionLocal, project_entry=Path(__file__))
    service = ProviderExecutionAuthorityService(repository)
    if args.command == "promote-reviewed-execution":
        _, candidate = _candidate_from_directory(args.infer_unique_candidate_from, project_root=REPOSITORY_ROOT)
        paths = (
            args.c0_code_attestation,
            args.c0_security_attestation,
            args.c1_code_attestation,
            args.c1_security_attestation,
        )
        loaded = validate_review_attestations(paths, project_root=REPOSITORY_ROOT)
        request = build_promotion_request(
            candidate=candidate,
            attestations=tuple(zip(paths, loaded, strict=True)),
        )
        projection = await promote_reviewed_execution(
            request,
            projection_root=args.projection_root,
            authority_service=service,
        )
        return {"result": "pass", "projection": projection.relative_to(REPOSITORY_ROOT).as_posix()}
    if args.command == "promotion-status":
        async with SessionLocal() as session:
            count = await session.scalar(select(func.count()).select_from(ProviderExecutionPromotion))
        if args.require_absent:
            if count != 0:
                raise GateRefusal("promotion_unexpected")
            return {"result": "pass", "promotion": "absent"}
        if not args.require_current or count != 1:
            raise GateRefusal("promotion_not_current")
        promotion = await service.require_current_promotion()
        if args.infer_unique_candidate_from is not None:
            _, candidate = _candidate_from_directory(args.infer_unique_candidate_from, project_root=REPOSITORY_ROOT)
            if (
                promotion.protected_code_c1_commit != candidate.protected_code_c1_commit
                or promotion.protected_code_c1_tree_hash != candidate.protected_code_c1_tree_hash
                or promotion.c0_to_c1_diff_hash != candidate.c0_to_c1_diff_hash
            ):
                raise GateRefusal("promotion_candidate_mismatch")
        return {"result": "pass", "promotion_id": str(promotion.promotion_id)}
    verifier = verify_candidate_live_state if args.command == "candidate" else verify_selected_pass_live_state
    return await verifier(
        args,
        service=service,
        repository=repository,
    )


async def _main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        if args.command == "seal-review-attestation":
            path = seal_review_attestation(
                stage=args.stage,
                kind=args.kind,
                collaboration_canonical_task_name=args.collaboration_canonical_task_name,
                actual_agent_role=args.actual_agent_role,
                workflow_invocation=args.workflow_invocation,
                standard_artifact_path=args.standard_artifact,
                gate_report_path=args.gate_report,
                output_root=args.output_root,
            )
            result = {"result": "pass", "attestation": path.relative_to(REPOSITORY_ROOT).as_posix()}
        elif args.command == "review-attestations":
            values = validate_review_attestations(
                (args.code_attestation, args.security_attestation),
                require_stage=args.require_stage,
                require_current_protected_base=args.require_current_protected_base,
            )
            result = {"result": "pass", "attestations": len(values)}
        elif args.command == "promotion-candidate":
            path = create_promotion_candidate(
                c0_code_attestation=args.c0_code_attestation,
                c0_security_attestation=args.c0_security_attestation,
                output_root=args.output_root,
            )
            result = {"result": "pass", "candidate": path.relative_to(REPOSITORY_ROOT).as_posix()}
        else:
            result = await _run_db_command(args)
    except (GateRefusal, ProviderExecutionAuthorityError, ValidationError) as exc:
        reason = getattr(exc, "reason_code", None) or str(exc)
        print(json.dumps({"error": "phase64_5_gate_refused", "reason_code": reason}, sort_keys=True))
        return 4
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(_main()))
