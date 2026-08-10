"""Provider-only RAG format-parity retrieval evaluation adapter."""

from __future__ import annotations

import argparse
import asyncio
from datetime import UTC, datetime, timedelta
import json
from pathlib import Path
import sys
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.db.models import EvidenceIdentityRollout, RagEvaluationRound, Tenant
from src.db.session import SessionLocal
from src.rag.embedder import EmbeddingService
from src.rag.evaluation.contracts import (
    EvaluationOutcome,
    FormatParityContractError,
    FormatParityDataset,
    load_format_parity_contract,
)
from src.rag.evaluation.retrieval_rounds import (
    PrerequisiteStatusV1,
    RetrievalParityRunV1,
    run_retrieval_parity,
)
from src.rag.parsers.runtime import check_ocr_runtime
from src.repositories.rag_evaluation_round_repo import (
    FORMAT_PARITY_OWNER_MARKER,
    FORMAT_PARITY_TENANT_ID,
    EvaluationIsolationError,
    EvaluationRoundIdentity,
    RagEvaluationRoundRepository,
)


EVALUATION_TENANT_NAME = "MOCA RAG Format Parity Evaluation"
EVALUATION_TENANT_STATUS = "evaluation_only"
DEFAULT_MANIFEST = "evaluation/rag_sources/format_parity_manifest.jsonl"
DEFAULT_GOLD = "evaluation/golden/rag_format_parity_gold.json"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run isolated provider-backed RAG format parity")
    parser.add_argument("--mode", choices=("provider",), required=True)
    parser.add_argument("--manifest", default=DEFAULT_MANIFEST)
    parser.add_argument("--gold", default=DEFAULT_GOLD)
    parser.add_argument("--tenant-id", required=True)
    parser.add_argument("--owner-marker", required=True)
    parser.add_argument("--run-token", required=True)
    parser.add_argument("--expected-rollout-version", type=int, required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--generated-at", required=True)
    return parser.parse_args(argv)


def validate_provider_arguments(args: argparse.Namespace) -> UUID:
    try:
        tenant_id = UUID(str(args.tenant_id))
        run_token = UUID(str(args.run_token))
        datetime.fromisoformat(str(args.generated_at).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        raise EvaluationIsolationError("provider_arguments_invalid") from None
    if (
        args.mode != "provider"
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


def _build_execution_error_result(
    *, dataset: FormatParityDataset, run_token: UUID, generated_at: str, reason_code: str
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
                name="evaluation_isolation",
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
    except FormatParityContractError as exc:
        empty = _empty_dataset()
        if exc.reason_code in {"manifest_file_invalid", "gold_file_invalid", "fixture_file_invalid"}:
            return build_unavailable_result(
                dataset=empty,
                run_token=run_token,
                generated_at=args.generated_at,
                missing=("evaluation_contract",),
            )
        return _build_execution_error_result(
            dataset=empty,
            run_token=run_token,
            generated_at=args.generated_at,
            reason_code="evaluation_contract_invalid",
        )

    missing: list[str] = []
    if not (settings.dashscope_api_key or "").strip():
        missing.append("embedding_provider")
    ocr = check_ocr_runtime(required_languages=("chi_sim", "eng"))
    if not ocr.available:
        missing.append("ocr_traineddata")

    owner: EvaluationRoundIdentity | None = None
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
                owner = await _claim_or_resume(
                    session,
                    run_token=run_token,
                    expected_rollout_version=args.expected_rollout_version,
                )
            return await run_retrieval_parity(
                dataset,
                session=session,
                embedder=EmbeddingService(),
                owner=owner,
                generated_at=args.generated_at,
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
        if owner is None:
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
) -> EvaluationRoundIdentity:
    active_rows = list(
        (
            await session.execute(
                select(RagEvaluationRound)
                .where(
                    RagEvaluationRound.tenant_id == FORMAT_PARITY_TENANT_ID,
                    RagEvaluationRound.state.not_in(("completed", "abandoned")),
                )
                .with_for_update()
            )
        )
        .scalars()
        .all()
    )
    if len(active_rows) > 1:
        raise EvaluationIsolationError("active_round_cardinality")
    if active_rows:
        row = active_rows[0]
        if (
            row.owner_marker != FORMAT_PARITY_OWNER_MARKER
            or row.run_token != run_token
            or row.round_format != "markdown"
            or row.expected_rollout_version != expected_rollout_version
            or tuple(row.doc_keys_json)
            != (
                "eval_refund_eligibility_and_return",
                "eval_quality_compensation_and_approval",
                "eval_cross_border_and_digital_goods",
            )
            or row.lease_expires_at <= datetime.now(UTC)
        ):
            raise EvaluationIsolationError("active_round_mismatch")
        return EvaluationRoundIdentity(
            round_id=row.id,
            tenant_id=row.tenant_id,
            owner_marker=row.owner_marker,
            run_token=row.run_token,
            round_token=row.round_token,
            round_format=row.round_format,
            state_version=row.state_version,
            next_document_index=row.next_document_index,
            expected_rollout_version=row.expected_rollout_version,
        )
    repository = RagEvaluationRoundRepository(session)
    return await repository.create_round(
        run_token=run_token,
        round_token=uuid5(NAMESPACE_URL, f"{run_token}:markdown"),
        round_format="markdown",
        lease_expires_at=datetime.now(UTC) + timedelta(hours=2),
        expected_rollout_version=expected_rollout_version,
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


async def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        result = await run_provider(args)
    except EvaluationIsolationError:
        return 2
    _write_result(Path(args.output), result)
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
        }
        else 2
    )


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
