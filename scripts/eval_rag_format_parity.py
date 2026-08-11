"""Provider-only RAG format-parity retrieval evaluation adapter."""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import time
from typing import Any, Literal
from uuid import NAMESPACE_URL, UUID, uuid5

from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.db.models import EvidenceIdentityRollout, Tenant
from src.db.session import SessionLocal
from src.knowledge.config import (
    MIN_SIMILARITY_THRESHOLD,
    QUERY_REWRITE_CONFIG_VERSION,
    RERANK_CONFIG_VERSION,
    RETRIEVAL_CONFIG_VERSION,
)
from src.knowledge.retrieval import (
    FUZZY_CANDIDATE_TOP_K,
    ORIGINAL_QUERY_TOP_K,
    RRF_K,
    SPARSE_CANDIDATE_TOP_K,
)
from src.rag.embedder import EmbeddingService
from src.rag.evaluation.contracts import (
    EvaluationOutcome,
    FormatParityContractError,
    FormatParityDataset,
    load_format_parity_contract,
)
from src.rag.evaluation.parser_parity import evaluate_parser_parity
from src.rag.evaluation.reporting import (
    FormatParityReportV1,
    FormatParityRuntimeConfigV1,
    build_format_parity_report,
    load_format_parity_report,
    render_markdown,
)
from src.rag.evaluation.retrieval_rounds import (
    PrerequisiteStatusV1,
    RetrievalParityRunV1,
    rebuild_completed_retrieval_parity,
    run_retrieval_parity,
)
from src.rag.ingestion import CharacterCompatibilityAssembler, PolicyInputAssembler
from src.rag.parsers.runtime import check_ocr_runtime
from src.rag.policy_embedding_input import PolicyEmbeddingInputAssembler
from src.repositories.rag_evaluation_round_repo import (
    FORMAT_PARITY_OWNER_MARKER,
    FORMAT_PARITY_TENANT_ID,
    EvaluationIsolationError,
    EvaluationRoundIdentity,
    RagEvaluationRoundRepository,
    validate_run_sequence,
)


EVALUATION_TENANT_NAME = "MOCA RAG Format Parity Evaluation"
EVALUATION_TENANT_STATUS = "evaluation_only"
DEFAULT_MANIFEST = "evaluation/rag_sources/format_parity_manifest.jsonl"
DEFAULT_GOLD = "evaluation/golden/rag_format_parity_gold.json"
CANONICAL_JSON_NAME = "baseline.json"
CANONICAL_MARKDOWN_NAME = "baseline.md"


def _token_candidate() -> PolicyInputAssembler:
    """Return the sole token-aware parsed-block assembler for Phase64.3/64.4 evaluation."""
    return PolicyEmbeddingInputAssembler()


def _character_baseline() -> PolicyInputAssembler:
    """Return the only explicitly named character incumbent for later same-run A/B."""
    return CharacterCompatibilityAssembler()


class RetrievalRunFixtureIdentityV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    doc_key: str
    format: Literal["markdown", "digital_pdf", "scanned_pdf"]
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class RetrievalRunIdentityV1(BaseModel):
    """Allowlisted identity sealed into every durable evaluation round."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["rag_format_parity_run_identity.v1"] = "rag_format_parity_run_identity.v1"
    manifest_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    gold_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    fixtures: tuple[RetrievalRunFixtureIdentityV1, ...]
    generator_identity_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    baseline_identity: str = Field(pattern=r"^[0-9a-f]{64}$")
    generated_at: str
    effective_at: str
    execution_mode: Literal["provider", "full-provider"]
    embedding_provider: Literal["dashscope"] = "dashscope"
    embedding_model: str
    embedding_dimensions: int = Field(gt=0)
    retrieval_config_version: str
    rrf_config: str
    rewrite_config: str
    reranker_config: str
    no_evidence_threshold: float = Field(ge=0.0, le=1.0)
    tenant_id: str
    owner_marker: str
    expected_rollout_version: int = Field(gt=0)


@dataclass(frozen=True)
class ClaimOrResumeOutcome:
    owner: EvaluationRoundIdentity | None
    completed_results: tuple[dict[str, Any], ...]
    run_identity_hash: str

    def __post_init__(self) -> None:
        completed = self.owner is None
        if (
            not re_full_sha256(self.run_identity_hash)
            or completed != (len(self.completed_results) == 3)
            or (self.owner is not None and self.owner.run_identity_hash != self.run_identity_hash)
        ):
            raise EvaluationIsolationError("run_sequence_outcome_invalid")


class DiagnosticInputIdentityV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    manifest_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    gold_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    fixture_hashes: tuple[str, ...]
    dataset_baseline_identity: str = Field(pattern=r"^[0-9a-f]{64}$")
    generator_identity_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


class FormatParityDiagnosticV1(BaseModel):
    """Baseline-ineligible unavailable/error output with no quality surface."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["rag_format_parity_diagnostic.v1"] = "rag_format_parity_diagnostic.v1"
    outcome: Literal["unavailable_prerequisite", "execution_error"]
    baseline_eligible: Literal[False] = False
    execution_kind: Literal["full_provider"] = "full_provider"
    generated_at: str
    command: Literal["scripts/eval_rag_format_parity.py --mode full-provider"] = (
        "scripts/eval_rag_format_parity.py --mode full-provider"
    )
    run_token: str = Field(min_length=1, max_length=64)
    inputs: DiagnosticInputIdentityV1
    prerequisites: tuple[str, ...]
    reason_codes: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_safe_diagnostic(self) -> FormatParityDiagnosticV1:
        allowed_prerequisites = {
            "canonical_rollout",
            "database_runtime",
            "database_schema",
            "embedding_provider",
            "evaluation_contract",
            "evaluation_tenant",
            "ocr_traineddata",
            "provider_runtime",
        }
        if any(item not in allowed_prerequisites for item in self.prerequisites):
            raise ValueError("unsafe_diagnostic_prerequisite")
        if any(not _safe_reason_code(item) == item for item in self.reason_codes):
            raise ValueError("unsafe_diagnostic_reason")
        return self


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run isolated provider-backed RAG format parity")
    parser.add_argument("--mode", choices=("provider", "full-provider"), required=True)
    parser.add_argument("--manifest", default=DEFAULT_MANIFEST)
    parser.add_argument("--gold", default=DEFAULT_GOLD)
    parser.add_argument("--tenant-id", required=True)
    parser.add_argument("--owner-marker", required=True)
    parser.add_argument("--run-token", required=True)
    parser.add_argument("--expected-rollout-version", type=int, required=True)
    parser.add_argument("--output")
    parser.add_argument("--output-dir")
    parser.add_argument("--diagnostic-output")
    parser.add_argument("--generated-at", default=None)
    args = parser.parse_args(argv)
    if args.generated_at is None:
        args.generated_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    if args.mode == "provider" and not args.output:
        parser.error("--output is required for provider mode")
    if args.mode == "full-provider" and (not args.output_dir or not args.diagnostic_output):
        parser.error("--output-dir and --diagnostic-output are required for full-provider mode")
    return args


def validate_provider_arguments(args: argparse.Namespace) -> UUID:
    try:
        tenant_id = UUID(str(args.tenant_id))
        run_token = UUID(str(args.run_token))
        datetime.fromisoformat(str(args.generated_at).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        raise EvaluationIsolationError("provider_arguments_invalid") from None
    if (
        args.mode not in {"provider", "full-provider"}
        or tenant_id != FORMAT_PARITY_TENANT_ID
        or args.owner_marker != FORMAT_PARITY_OWNER_MARKER
        or run_token.int == 0
        or args.expected_rollout_version <= 0
    ):
        raise EvaluationIsolationError("provider_arguments_invalid")
    return run_token


def build_unavailable_result(
    *,
    dataset: FormatParityDataset,
    run_token: UUID,
    generated_at: str,
    missing: tuple[str, ...],
) -> RetrievalParityRunV1:
    names = tuple(sorted(dict.fromkeys(_safe_prerequisite_name(item) for item in missing)))
    return RetrievalParityRunV1(
        mode="provider",
        baseline_eligible=False,
        outcome=EvaluationOutcome.UNAVAILABLE_PREREQUISITE,
        generated_at=generated_at,
        tenant_id=str(FORMAT_PARITY_TENANT_ID),
        owner_marker=FORMAT_PARITY_OWNER_MARKER,
        run_token=str(run_token),
        manifest_hash=dataset.manifest_hash,
        gold_hash=dataset.gold_hash,
        baseline_identity=dataset.baseline_identity,
        rounds=(),
        prerequisites=tuple(
            PrerequisiteStatusV1(name=name, available=False, reason_code="prerequisite_unavailable") for name in names
        ),
    )


def build_diagnostic(
    *,
    dataset: FormatParityDataset,
    outcome: EvaluationOutcome,
    generated_at: str,
    run_token: str | UUID,
    prerequisites: tuple[str, ...],
    reason_codes: tuple[str, ...],
) -> FormatParityDiagnosticV1:
    if outcome not in {
        EvaluationOutcome.UNAVAILABLE_PREREQUISITE,
        EvaluationOutcome.EXECUTION_ERROR,
    }:
        raise ValueError("diagnostic_outcome_invalid")
    generator_hash = _generator_identity_hash(dataset)
    return FormatParityDiagnosticV1(
        outcome=outcome.value,
        generated_at=str(generated_at),
        run_token=str(run_token),
        inputs=DiagnosticInputIdentityV1(
            manifest_hash=dataset.manifest_hash,
            gold_hash=dataset.gold_hash,
            fixture_hashes=tuple(sorted(dataset.fixture_hashes.values())),
            dataset_baseline_identity=dataset.baseline_identity,
            generator_identity_hash=generator_hash,
        ),
        prerequisites=tuple(sorted({_safe_prerequisite_name(item) for item in prerequisites})),
        reason_codes=tuple(sorted({_safe_reason_code(item) for item in reason_codes})),
    )


def _generator_identity_hash(dataset: FormatParityDataset) -> str:
    if not dataset.policies:
        return "0" * 64
    identities = {
        json.dumps(
            policy.generator_identity.model_dump(mode="json"),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        for policy in dataset.policies
    }
    if len(identities) != 1:
        raise EvaluationIsolationError("generator_identity_mismatch")
    return hashlib.sha256(next(iter(identities)).encode("utf-8")).hexdigest()


def re_full_sha256(value: str) -> bool:
    return len(value) == 64 and all(character in "0123456789abcdef" for character in value)


def _rrf_config_identity() -> str:
    return f"rrf_k={RRF_K};dense={ORIGINAL_QUERY_TOP_K};sparse={SPARSE_CANDIDATE_TOP_K};fuzzy={FUZZY_CANDIDATE_TOP_K}"


def build_run_identity_hash(
    dataset: FormatParityDataset,
    *,
    args: argparse.Namespace,
) -> str:
    """Hash only stable allowlisted values; never persist paths, DSNs, or secrets."""

    identity = RetrievalRunIdentityV1(
        manifest_hash=dataset.manifest_hash,
        gold_hash=dataset.gold_hash,
        fixtures=tuple(
            RetrievalRunFixtureIdentityV1(
                doc_key=policy.doc_key,
                format=variant.format,
                sha256=variant.sha256,
            )
            for policy in dataset.policies
            for variant in policy.variants
        ),
        generator_identity_hash=_generator_identity_hash(dataset),
        baseline_identity=dataset.baseline_identity,
        generated_at=str(args.generated_at),
        effective_at=str(args.generated_at),
        execution_mode=args.mode,
        embedding_model=settings.embedding_model,
        embedding_dimensions=settings.embedding_dimensions,
        retrieval_config_version=RETRIEVAL_CONFIG_VERSION,
        rrf_config=_rrf_config_identity(),
        rewrite_config=f"{QUERY_REWRITE_CONFIG_VERSION}:enabled",
        reranker_config=f"{RERANK_CONFIG_VERSION}:enabled",
        no_evidence_threshold=MIN_SIMILARITY_THRESHOLD,
        tenant_id=str(args.tenant_id),
        owner_marker=str(args.owner_marker),
        expected_rollout_version=int(args.expected_rollout_version),
    )
    payload = json.dumps(
        identity.model_dump(mode="json"),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _build_execution_error_result(
    *,
    dataset: FormatParityDataset,
    run_token: UUID,
    generated_at: str,
    reason_code: str,
    prerequisite_name: str = "evaluation_isolation",
) -> RetrievalParityRunV1:
    return RetrievalParityRunV1(
        mode="provider",
        baseline_eligible=False,
        outcome=EvaluationOutcome.EXECUTION_ERROR,
        generated_at=generated_at,
        tenant_id=str(FORMAT_PARITY_TENANT_ID),
        owner_marker=FORMAT_PARITY_OWNER_MARKER,
        run_token=str(run_token),
        manifest_hash=dataset.manifest_hash,
        gold_hash=dataset.gold_hash,
        baseline_identity=dataset.baseline_identity,
        rounds=(),
        prerequisites=(
            PrerequisiteStatusV1(
                name=_safe_prerequisite_name(prerequisite_name),
                available=False,
                reason_code=_safe_reason_code(reason_code),
            ),
        ),
    )


async def run_provider(args: argparse.Namespace) -> RetrievalParityRunV1:
    run_token = validate_provider_arguments(args)
    try:
        dataset = load_format_parity_contract(
            Path(args.manifest),
            Path(args.gold),
            repository_root=Path.cwd(),
        )
    except FormatParityContractError:
        return _build_execution_error_result(
            dataset=_empty_dataset(),
            run_token=run_token,
            generated_at=args.generated_at,
            reason_code="evaluation_contract_invalid",
            prerequisite_name="evaluation_contract",
        )

    missing: list[str] = []
    if not (settings.dashscope_api_key or "").strip():
        missing.append("embedding_provider")
    ocr = check_ocr_runtime(required_languages=("chi_sim", "eng"))
    if not ocr.available:
        missing.append("ocr_traineddata")

    owner: EvaluationRoundIdentity | None = None
    claim_started = False
    try:
        async with SessionLocal() as session:
            db_missing = await asyncio.wait_for(
                _database_prerequisites(
                    session,
                    expected_rollout_version=args.expected_rollout_version,
                ),
                timeout=10,
            )
            missing.extend(db_missing)
            if missing:
                return build_unavailable_result(
                    dataset=dataset,
                    run_token=run_token,
                    generated_at=args.generated_at,
                    missing=tuple(missing),
                )
            async with session.begin():
                run_identity_hash = build_run_identity_hash(dataset, args=args)
                claim = await _claim_or_resume(
                    session,
                    run_token=run_token,
                    expected_rollout_version=args.expected_rollout_version,
                    run_identity_hash=run_identity_hash,
                )
                claim_started = True
            owner = claim.owner
            if owner is None:
                return rebuild_completed_retrieval_parity(
                    dataset,
                    completed_results=claim.completed_results,
                    generated_at=args.generated_at,
                    run_token=run_token,
                    run_identity_hash=claim.run_identity_hash,
                    expected_run_identity_hash=run_identity_hash,
                )
            return await run_retrieval_parity(
                dataset,
                session=session,
                embedder=EmbeddingService(),
                owner=owner,
                generated_at=args.generated_at,
                input_assembler=_token_candidate(),
            )
    except (TimeoutError, OSError):
        missing.append("database_runtime")
    except EvaluationIsolationError as exc:
        return _build_execution_error_result(
            dataset=dataset,
            run_token=run_token,
            generated_at=args.generated_at,
            reason_code=exc.reason_code,
        )
    except Exception:
        if not claim_started:
            missing.append("database_runtime")
        else:
            return _build_execution_error_result(
                dataset=dataset,
                run_token=run_token,
                generated_at=args.generated_at,
                reason_code="provider_execution_failed",
            )
    return build_unavailable_result(
        dataset=dataset,
        run_token=run_token,
        generated_at=args.generated_at,
        missing=tuple(missing),
    )


async def run_full_provider(
    args: argparse.Namespace,
) -> FormatParityReportV1 | FormatParityDiagnosticV1:
    """Run parser-direct plus real provider retrieval and build one result owner."""

    started = time.monotonic()
    run_token = validate_provider_arguments(args)
    try:
        dataset = load_format_parity_contract(
            Path(args.manifest),
            Path(args.gold),
            repository_root=Path.cwd(),
        )
    except FormatParityContractError:
        return build_diagnostic(
            dataset=_empty_dataset(),
            outcome=EvaluationOutcome.EXECUTION_ERROR,
            generated_at=args.generated_at,
            run_token=run_token,
            prerequisites=("evaluation_contract",),
            reason_codes=("evaluation_contract_invalid",),
        )

    missing: list[str] = []
    if not (settings.dashscope_api_key or "").strip():
        missing.append("embedding_provider")
    ocr = check_ocr_runtime(required_languages=("chi_sim", "eng"))
    if not ocr.available:
        missing.append("ocr_traineddata")

    try:
        async with SessionLocal() as session:
            try:
                database_missing = await asyncio.wait_for(
                    _database_prerequisites(
                        session,
                        expected_rollout_version=args.expected_rollout_version,
                    ),
                    timeout=10,
                )
            except (TimeoutError, OSError):
                database_missing = ("database_runtime",)
            except Exception:
                database_missing = ("database_runtime",)
            missing.extend(database_missing)
            if missing:
                return build_diagnostic(
                    dataset=dataset,
                    outcome=EvaluationOutcome.UNAVAILABLE_PREREQUISITE,
                    generated_at=args.generated_at,
                    run_token=run_token,
                    prerequisites=tuple(missing),
                    reason_codes=("prerequisite_unavailable",),
                )

            parser_started = time.monotonic()
            parser_run = evaluate_parser_parity(dataset, generated_at=args.generated_at)
            parser_duration_ms = (time.monotonic() - parser_started) * 1000
            if parser_run.outcome in {
                EvaluationOutcome.UNAVAILABLE_PREREQUISITE,
                EvaluationOutcome.EXECUTION_ERROR,
            }:
                return build_diagnostic(
                    dataset=dataset,
                    outcome=parser_run.outcome,
                    generated_at=args.generated_at,
                    run_token=run_token,
                    prerequisites=tuple(item.name for item in parser_run.prerequisites if item.status == "unavailable"),
                    reason_codes=tuple(
                        item.reason_code for item in parser_run.prerequisites if item.status == "unavailable"
                    )
                    or ("parser_execution_failed",),
                )

            run_identity_hash = build_run_identity_hash(dataset, args=args)
            async with session.begin():
                claim = await _claim_or_resume(
                    session,
                    run_token=run_token,
                    expected_rollout_version=args.expected_rollout_version,
                    run_identity_hash=run_identity_hash,
                )
            retrieval_started = time.monotonic()
            if claim.owner is None:
                retrieval_run = rebuild_completed_retrieval_parity(
                    dataset,
                    completed_results=claim.completed_results,
                    generated_at=args.generated_at,
                    run_token=run_token,
                    run_identity_hash=claim.run_identity_hash,
                    expected_run_identity_hash=run_identity_hash,
                )
            else:
                retrieval_run = await run_retrieval_parity(
                    dataset,
                    session=session,
                    embedder=EmbeddingService(),
                    owner=claim.owner,
                    generated_at=args.generated_at,
                    input_assembler=_token_candidate(),
                )
            retrieval_duration_ms = (time.monotonic() - retrieval_started) * 1000
    except EvaluationIsolationError as exc:
        return build_diagnostic(
            dataset=dataset,
            outcome=EvaluationOutcome.EXECUTION_ERROR,
            generated_at=args.generated_at,
            run_token=run_token,
            prerequisites=(),
            reason_codes=(exc.reason_code,),
        )
    except Exception:
        return build_diagnostic(
            dataset=dataset,
            outcome=EvaluationOutcome.EXECUTION_ERROR,
            generated_at=args.generated_at,
            run_token=run_token,
            prerequisites=(),
            reason_codes=("provider_execution_failed",),
        )

    if retrieval_run.outcome not in {
        EvaluationOutcome.COMPLETED_PASS,
        EvaluationOutcome.COMPLETED_QUALITY_FAIL,
    }:
        return build_diagnostic(
            dataset=dataset,
            outcome=retrieval_run.outcome,
            generated_at=args.generated_at,
            run_token=run_token,
            prerequisites=tuple(item.name for item in retrieval_run.prerequisites if not item.available),
            reason_codes=tuple(
                round_result.reason_code for round_result in retrieval_run.rounds if round_result.reason_code
            )
            or ("provider_execution_failed",),
        )

    total_duration_ms = (time.monotonic() - started) * 1000
    return _build_completed_report(
        args=args,
        dataset=dataset,
        parser_run=parser_run,
        retrieval_run=retrieval_run,
        parser_duration_ms=parser_duration_ms,
        retrieval_duration_ms=retrieval_duration_ms,
        total_duration_ms=total_duration_ms,
    )


def _build_completed_report(
    *,
    args: argparse.Namespace,
    dataset: FormatParityDataset,
    parser_run: object,
    retrieval_run: RetrievalParityRunV1,
    parser_duration_ms: float,
    retrieval_duration_ms: float,
    total_duration_ms: float,
) -> FormatParityReportV1 | FormatParityDiagnosticV1:
    try:
        runtime_config = _runtime_config(
            args=args,
            dataset=dataset,
            parser_run=parser_run,
            parser_duration_ms=parser_duration_ms,
            retrieval_duration_ms=retrieval_duration_ms,
            total_duration_ms=total_duration_ms,
        )
    except (OSError, ValueError):
        return build_diagnostic(
            dataset=dataset,
            outcome=EvaluationOutcome.EXECUTION_ERROR,
            generated_at=args.generated_at,
            run_token=args.run_token,
            prerequisites=(),
            reason_codes=("report_config_failed",),
        )
    try:
        report = build_format_parity_report(
            dataset=dataset,
            parser_run=parser_run,
            retrieval_run=retrieval_run,
            runtime_config=runtime_config,
            generated_at=args.generated_at,
        )
    except (OSError, ValueError):
        return build_diagnostic(
            dataset=dataset,
            outcome=EvaluationOutcome.EXECUTION_ERROR,
            generated_at=args.generated_at,
            run_token=args.run_token,
            prerequisites=(),
            reason_codes=("report_build_failed",),
        )
    if not report.baseline_eligible or report.outcome not in {
        EvaluationOutcome.COMPLETED_PASS,
        EvaluationOutcome.COMPLETED_QUALITY_FAIL,
    }:
        return build_diagnostic(
            dataset=dataset,
            outcome=(
                report.outcome
                if report.outcome
                in {
                    EvaluationOutcome.UNAVAILABLE_PREREQUISITE,
                    EvaluationOutcome.EXECUTION_ERROR,
                }
                else EvaluationOutcome.EXECUTION_ERROR
            ),
            generated_at=args.generated_at,
            run_token=args.run_token,
            prerequisites=tuple(item.name for item in report.prerequisites if item.status == "unavailable"),
            reason_codes=report.safe_reason_codes or ("canonical_baseline_ineligible",),
        )
    return report


def _runtime_config(
    *,
    args: argparse.Namespace,
    dataset: FormatParityDataset,
    parser_run: object,
    parser_duration_ms: float,
    retrieval_duration_ms: float,
    total_duration_ms: float,
) -> FormatParityRuntimeConfigV1:
    runtime_versions = tuple(getattr(parser_run, "runtime_versions", ()))
    parser_toolchain = tuple(
        sorted(f"{item.name}@{item.version}" for item in runtime_versions if getattr(item, "kind", None) == "parser")
    ) or ("moca_parser_registry@unknown",)
    ocr_toolchain = tuple(
        sorted(
            f"{item.name}@{item.version}:{item.language or 'unspecified'}"
            for item in runtime_versions
            if getattr(item, "kind", None) == "ocr"
        )
    ) or ("tesseract@unknown:chi_sim+eng",)
    temp_directory_mode = _ocr_temp_directory_mode()
    temp_directory_command = (
        "TMPDIR_MODE=explicit_macos_private_tmp " if temp_directory_mode == "explicit_macos_private_tmp" else ""
    )
    command = (
        f"{temp_directory_command}scripts/eval_rag_format_parity.py --mode full-provider "
        f"--manifest {args.manifest} --gold {args.gold} "
        f"--tenant-id {args.tenant_id} --owner-marker {args.owner_marker} "
        f"--run-token {args.run_token} --expected-rollout-version {args.expected_rollout_version}"
    )
    return FormatParityRuntimeConfigV1(
        command=command,
        execution_kind="full_provider",
        tenant_id=str(args.tenant_id),
        owner_marker=str(args.owner_marker),
        run_token=str(args.run_token),
        expected_rollout_version=int(args.expected_rollout_version),
        generator_identity_hash=_generator_identity_hash(dataset),
        embedding_provider="dashscope",
        embedding_model=settings.embedding_model,
        embedding_dimensions=settings.embedding_dimensions,
        retrieval_config_version=RETRIEVAL_CONFIG_VERSION,
        rrf_config=_rrf_config_identity(),
        rewrite_config=f"{QUERY_REWRITE_CONFIG_VERSION}:enabled",
        reranker_config=f"{RERANK_CONFIG_VERSION}:enabled",
        no_evidence_threshold=MIN_SIMILARITY_THRESHOLD,
        parser_toolchain=parser_toolchain,
        ocr_toolchain=ocr_toolchain,
        ocr_temp_directory_mode=temp_directory_mode,
        parser_duration_ms=round(parser_duration_ms, 3),
        retrieval_duration_ms=round(retrieval_duration_ms, 3),
        total_duration_ms=round(total_duration_ms, 3),
        embedding_tokens=None,
        embedding_tokens_status="unavailable",
    )


def _ocr_temp_directory_mode() -> Literal["platform_default", "explicit_macos_private_tmp"]:
    """Record the safe runtime identity, never the caller's arbitrary path."""

    configured = os.environ.get("TMPDIR")
    if configured == "/private/tmp":
        return "explicit_macos_private_tmp"
    return "platform_default"


async def _database_prerequisites(session: AsyncSession, *, expected_rollout_version: int) -> tuple[str, ...]:
    missing: list[str] = []
    schema = (
        await session.execute(
            text(
                "SELECT to_regclass('public.rag_evaluation_rounds') IS NOT NULL, "
                "EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector'), "
                "(SELECT version_num FROM alembic_version LIMIT 1)"
            )
        )
    ).one()
    if not bool(schema[0]) or not bool(schema[1]) or schema[2] != "029_phase64_3_rag_eval_rounds":
        missing.append("database_schema")
    tenant = await session.get(Tenant, FORMAT_PARITY_TENANT_ID)
    if tenant is None or tenant.name != EVALUATION_TENANT_NAME or tenant.status != EVALUATION_TENANT_STATUS:
        missing.append("evaluation_tenant")
    rollout = await session.get(EvidenceIdentityRollout, 1)
    if (
        rollout is None
        or rollout.rollout_version != expected_rollout_version
        or not rollout.canonical_reads_enabled
        or rollout.dual_write_enabled_at is None
    ):
        missing.append("canonical_rollout")
    await session.rollback()
    return tuple(missing)


async def _claim_or_resume(
    session: AsyncSession,
    *,
    run_token: UUID,
    expected_rollout_version: int,
    run_identity_hash: str,
) -> ClaimOrResumeOutcome:
    repository = RagEvaluationRoundRepository(session)
    now = datetime.now(UTC)
    rows = await repository.lock_run_rows(run_token)
    sequence = validate_run_sequence(
        rows,
        run_token=run_token,
        expected_rollout_version=expected_rollout_version,
        run_identity_hash=run_identity_hash,
        now=now,
    )
    if sequence.active is not None:
        return ClaimOrResumeOutcome(
            owner=sequence.active,
            completed_results=sequence.completed_results,
            run_identity_hash=run_identity_hash,
        )
    if sequence.next_format is None:
        return ClaimOrResumeOutcome(
            owner=None,
            completed_results=sequence.completed_results,
            run_identity_hash=run_identity_hash,
        )
    next_format = sequence.next_format
    owner = await repository.create_round(
        run_token=run_token,
        round_token=uuid5(NAMESPACE_URL, f"{run_token}:{next_format}"),
        round_format=next_format,
        run_identity_hash=run_identity_hash,
        lease_expires_at=now + timedelta(hours=2),
        expected_rollout_version=expected_rollout_version,
    )
    return ClaimOrResumeOutcome(
        owner=owner,
        completed_results=sequence.completed_results,
        run_identity_hash=run_identity_hash,
    )


def _empty_dataset() -> FormatParityDataset:
    return FormatParityDataset(
        manifest_hash="0" * 64,
        gold_hash="0" * 64,
        fixture_hashes={},
        policies=(),
        baseline_identity="0" * 64,
    )


def _safe_prerequisite_name(value: str) -> str:
    allowed = {
        "canonical_rollout",
        "database_runtime",
        "database_schema",
        "embedding_provider",
        "evaluation_contract",
        "evaluation_tenant",
        "ocr_traineddata",
    }
    return value if value in allowed else "provider_runtime"


def _safe_reason_code(value: str) -> str:
    text_value = "".join(character for character in str(value) if character.isalnum() or character in "_:-")
    return (text_value or "execution_error")[:64]


def _write_result(path: Path, result: RetrievalParityRunV1) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def persist_full_provider_result(
    *,
    result: FormatParityReportV1 | FormatParityDiagnosticV1,
    output_dir: Path,
    diagnostic_output: Path,
) -> tuple[Path, ...]:
    """Persist either one diagnostic or the canonical pair, never both."""

    canonical_json = output_dir / CANONICAL_JSON_NAME
    canonical_markdown = output_dir / CANONICAL_MARKDOWN_NAME
    diagnostic_resolved = diagnostic_output.resolve(strict=False)
    if diagnostic_resolved in {
        canonical_json.resolve(strict=False),
        canonical_markdown.resolve(strict=False),
    }:
        raise ValueError("diagnostic_path_aliases_canonical")

    if isinstance(result, FormatParityDiagnosticV1):
        payload = (
            json.dumps(
                result.model_dump(mode="json"),
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            ).encode("utf-8")
            + b"\n"
        )
        _atomic_write_bytes(diagnostic_output, payload)
        persisted = FormatParityDiagnosticV1.model_validate_json(diagnostic_output.read_text(encoding="utf-8"))
        if persisted != result:
            raise ValueError("diagnostic_round_trip_mismatch")
        return (diagnostic_output,)

    if (
        not result.baseline_eligible
        or result.config.execution_kind != "full_provider"
        or result.outcome
        not in {
            EvaluationOutcome.COMPLETED_PASS,
            EvaluationOutcome.COMPLETED_QUALITY_FAIL,
        }
    ):
        raise ValueError("canonical_baseline_ineligible")
    canonical = result.model_dump(mode="json")
    json_payload = (
        json.dumps(
            canonical,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ).encode("utf-8")
        + b"\n"
    )
    markdown_payload = render_markdown(canonical).encode("utf-8")
    _atomic_write_canonical_pair(
        json_path=canonical_json,
        markdown_path=canonical_markdown,
        json_payload=json_payload,
        markdown_payload=markdown_payload,
    )
    loaded = load_format_parity_report(canonical_json)
    if canonical_markdown.read_text(encoding="utf-8") != render_markdown(loaded.model_dump(mode="json")):
        raise ValueError("canonical_projection_round_trip_mismatch")
    return canonical_json, canonical_markdown


def _persist_completed_outcome(
    *,
    result: FormatParityReportV1 | FormatParityDiagnosticV1,
    output_dir: Path,
    diagnostic_output: Path,
) -> FormatParityReportV1 | FormatParityDiagnosticV1:
    try:
        persist_full_provider_result(
            result=result,
            output_dir=output_dir,
            diagnostic_output=diagnostic_output,
        )
        return result
    except (OSError, ValueError):
        if isinstance(result, FormatParityDiagnosticV1):
            raise
        diagnostic = FormatParityDiagnosticV1(
            outcome="execution_error",
            generated_at=result.generated_at,
            run_token=result.config.run_token,
            inputs=DiagnosticInputIdentityV1(
                manifest_hash=result.inputs.manifest_hash,
                gold_hash=result.inputs.gold_hash,
                fixture_hashes=tuple(sorted(item.sha256 for item in result.inputs.fixture_hashes)),
                dataset_baseline_identity=result.inputs.dataset_baseline_identity,
                generator_identity_hash=result.inputs.generator_identity_hash,
            ),
            prerequisites=(),
            reason_codes=("report_persist_failed",),
        )
        persist_full_provider_result(
            result=diagnostic,
            output_dir=output_dir,
            diagnostic_output=diagnostic_output,
        )
        return diagnostic


def _atomic_write_canonical_pair(
    *,
    json_path: Path,
    markdown_path: Path,
    json_payload: bytes,
    markdown_payload: bytes,
) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_temp = _write_temp(json_path, json_payload)
    markdown_temp = _write_temp(markdown_path, markdown_payload)
    old_json = json_path.read_bytes() if json_path.exists() else None
    old_markdown = markdown_path.read_bytes() if markdown_path.exists() else None
    try:
        staged = load_format_parity_report(json_temp)
        if markdown_temp.read_text(encoding="utf-8") != render_markdown(staged.model_dump(mode="json")):
            raise ValueError("canonical_projection_mismatch")
        os.replace(json_temp, json_path)
        os.replace(markdown_temp, markdown_path)
    except Exception:
        _restore_file(json_path, old_json)
        _restore_file(markdown_path, old_markdown)
        raise
    finally:
        for temporary in (json_temp, markdown_temp):
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass


def _atomic_write_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = _write_temp(path, payload)
    try:
        os.replace(temporary, path)
    finally:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass


def _write_temp(target: Path, payload: bytes) -> Path:
    with tempfile.NamedTemporaryFile(
        mode="wb",
        dir=target.parent,
        prefix=f".{target.name}.",
        suffix=".tmp",
        delete=False,
    ) as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
        return Path(stream.name)


def _restore_file(path: Path, payload: bytes | None) -> None:
    if payload is None:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass
        return
    path.write_bytes(payload)


async def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        if args.mode == "provider":
            result = await run_provider(args)
            _write_result(Path(args.output), result)
        else:
            result = await run_full_provider(args)
            result = _persist_completed_outcome(
                result=result,
                output_dir=Path(args.output_dir),
                diagnostic_output=Path(args.diagnostic_output),
            )
    except EvaluationIsolationError:
        return 2
    except (OSError, ValueError):
        return 2
    print(
        json.dumps(
            {
                "schema_version": result.schema_version,
                "outcome": result.outcome,
                "baseline_eligible": result.baseline_eligible,
            },
            sort_keys=True,
        )
    )
    return (
        0
        if result.outcome
        in {
            EvaluationOutcome.COMPLETED_PASS,
            EvaluationOutcome.COMPLETED_QUALITY_FAIL,
            "completed_pass",
            "completed_quality_fail",
        }
        else 2
    )


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
