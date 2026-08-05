"""Backfill and activate canonical immutable evidence reads.

Revision ID: 026_phase64_2_evidence_cutover
Revises: 025_phase64_2_immutable_evidence
Create Date: 2026-08-05

Deployment is staged: migration 025, real dual-write activation plus a fresh
health proof, then this migration. A direct unstaged upgrade intentionally
fails closed.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
import json
from uuid import uuid4

from alembic import op
import sqlalchemy as sa

from src.knowledge.text_hash import evidence_text_hash
from src.rag.versioning import build_policy_version_fingerprint

revision: str = "026_phase64_2_evidence_cutover"
down_revision: str | None = "025_phase64_2_immutable_evidence"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

_HEALTH_MAX_AGE = timedelta(minutes=5)
_RETENTION = timedelta(days=3650)


def upgrade() -> None:
    bind = op.get_bind()
    rollout = (
        bind.execute(
            sa.text(
                "SELECT rollout_version, dual_write_enabled_at, backfill_watermark_sequence, "
                "canonical_reads_enabled, audit_counts_json "
                "FROM evidence_identity_rollouts WHERE id = 1 FOR UPDATE"
            )
        )
        .mappings()
        .one()
    )
    if rollout["dual_write_enabled_at"] is None:
        raise RuntimeError("dual_write_enabled_at is null; deploy and activate dual-write before migration 026")
    _assert_health_current(dict(rollout["audit_counts_json"] or {}))
    expected_rollout_version = int(rollout["rollout_version"])
    watermark = rollout["backfill_watermark_sequence"]
    if watermark is None:
        watermark = int(bind.execute(sa.text("SELECT nextval('evidence_ingestion_write_seq')")).scalar_one())
        bind.execute(
            sa.text(
                "UPDATE evidence_identity_rollouts SET backfill_watermark_sequence = :watermark, "
                "audit_counts_json = audit_counts_json || CAST(:audit AS jsonb) "
                "WHERE id = 1 AND rollout_version = :expected_rollout_version"
            ),
            {
                "watermark": watermark,
                "expected_rollout_version": expected_rollout_version,
                "audit": json.dumps(
                    {
                        "backfill_status": "watermark_reserved",
                        "backfill_watermark_sequence": watermark,
                    }
                ),
            },
        )

    _, resolved_count, _ = _backfill_current_heads(bind, int(watermark))
    canonical_count, unresolved_count, reconciled_through = _reconcile_current_heads(bind, int(watermark))
    audit = json.dumps(
        {
            "backfill_status": "reconciled" if unresolved_count == 0 else "legacy_unresolved",
            "canonical_count": canonical_count,
            "resolved_count": resolved_count,
            "unresolved_count": unresolved_count,
            "reconciled_through_sequence": reconciled_through,
        }
    )
    if unresolved_count:
        bind.execute(
            sa.text(
                "UPDATE evidence_identity_rollouts SET canonical_reads_enabled = false, "
                "quarantine_reason = 'legacy_unresolved', audit_counts_json = audit_counts_json || CAST(:audit AS jsonb) "
                "WHERE id = 1 AND rollout_version = :expected_rollout_version"
            ),
            {"audit": audit, "expected_rollout_version": expected_rollout_version},
        )
        return

    # The initial FOR UPDATE lock remains held continuously across this last
    # reconciliation/zero-gap assertion and the CAS read activation.
    result = bind.execute(
        sa.text(
            "UPDATE evidence_identity_rollouts SET reconciled_through_sequence = :reconciled, "
            "canonical_reads_enabled = true, canonical_reads_enabled_at = CURRENT_TIMESTAMP, "
            "canonical_reads_disabled_at = NULL, quarantine_reason = NULL, "
            "audit_counts_json = audit_counts_json || CAST(:audit AS jsonb), "
            "rollout_version = rollout_version + 1 "
            "WHERE id = 1 AND rollout_version = :expected_rollout_version"
        ),
        {
            "reconciled": reconciled_through,
            "audit": audit,
            "expected_rollout_version": expected_rollout_version,
        },
    )
    if result.rowcount != 1:
        raise RuntimeError("stale rollout owner during canonical read activation")


def downgrade() -> None:
    state = (
        op.get_bind()
        .execute(
            sa.text(
                "SELECT canonical_reads_enabled, backfill_watermark_sequence, reconciled_through_sequence "
                "FROM evidence_identity_rollouts WHERE id = 1 FOR UPDATE"
            )
        )
        .one()
    )
    dependencies = (
        op.get_bind()
        .execute(
            sa.text(
                "SELECT EXISTS (SELECT 1 FROM policy_document_versions) "
                "OR EXISTS (SELECT 1 FROM policy_chunk_versions) "
                "OR EXISTS (SELECT 1 FROM evidence_snapshot_dependencies) "
                "OR EXISTS (SELECT 1 FROM agent_trace_events "
                "WHERE evidence_snapshot_refs_json IS NOT NULL AND evidence_snapshot_refs_json <> '[]'::jsonb)"
            )
        )
        .scalar_one()
    )
    if bool(state[0]) or state[1] is not None or state[2] is not None or dependencies:
        raise RuntimeError("refusing downgrade: immutable history, dependencies, snapshots, or canonical refs exist")


def _assert_health_current(audit: dict[str, object]) -> None:
    raw_checked_at = audit.get("dual_write_health_checked_at")
    if audit.get("dual_write_health") != "healthy" or not isinstance(raw_checked_at, str):
        raise RuntimeError("dual-write health proof is unavailable")
    try:
        checked_at = datetime.fromisoformat(raw_checked_at)
    except ValueError as exc:
        raise RuntimeError("dual-write health proof is invalid") from exc
    if checked_at.tzinfo is None:
        checked_at = checked_at.replace(tzinfo=UTC)
    if datetime.now(UTC) - checked_at.astimezone(UTC) > _HEALTH_MAX_AGE:
        raise RuntimeError("dual-write health proof is stale")


def _backfill_current_heads(bind: sa.Connection, watermark: int) -> tuple[int, int, int]:
    documents = bind.execute(
        sa.text(
            "SELECT id, tenant_id, doc_key, doc_type, title, effective_date, risk_level, version, content, "
            "source_type, source_checksum, parser_metadata_json, policy_version_fingerprint, evidence_write_sequence "
            "FROM policy_documents ORDER BY tenant_id, doc_key, id FOR UPDATE"
        )
    ).mappings()
    canonical_count = 0
    resolved_count = 0
    unresolved_count = 0
    for document in documents:
        chunks = list(
            bind.execute(
                sa.text(
                    "SELECT id, chunk_id, content, source_block_refs_json, ocr_metadata_json, evidence_write_sequence "
                    "FROM policy_chunks WHERE tenant_id = :tenant_id AND doc_id = :doc_id "
                    "ORDER BY tenant_id, doc_id, id FOR UPDATE"
                ),
                {"tenant_id": document["tenant_id"], "doc_id": document["id"]},
            ).mappings()
        )
        reason = _legacy_failure(document, chunks)
        if reason is not None:
            _mark_unresolved(bind, document, reason)
            unresolved_count += 1
            continue
        existing = (
            bind.execute(
                sa.text(
                    "SELECT id, content_hash FROM policy_document_versions WHERE tenant_id = :tenant_id "
                    "AND scope_type = 'tenant_policy' AND scope_id = CAST(:tenant_id AS VARCHAR) "
                    "AND doc_key = :doc_key AND document_version = :document_version"
                ),
                {
                    "tenant_id": document["tenant_id"],
                    "doc_key": document["doc_key"],
                    "document_version": document["version"],
                },
            )
            .mappings()
            .all()
        )
        if len(existing) > 1:
            _mark_unresolved(bind, document, "ambiguous_immutable_document")
            unresolved_count += 1
            continue
        if not existing:
            document_version_id = uuid4()
            bind.execute(
                sa.text(
                    "INSERT INTO policy_document_versions "
                    "(id, tenant_id, policy_document_id, scope_type, scope_id, doc_key, document_version, "
                    "content, content_hash, source_locator_json, lifecycle_status, retention_until) "
                    "VALUES (:id, :tenant_id, :policy_document_id, 'tenant_policy', CAST(:tenant_id AS VARCHAR), "
                    ":doc_key, :document_version, :content, :content_hash, CAST(:locator AS jsonb), 'active', :retention)"
                ),
                {
                    "id": document_version_id,
                    "tenant_id": document["tenant_id"],
                    "policy_document_id": document["id"],
                    "doc_key": document["doc_key"],
                    "document_version": document["version"],
                    "content": document["content"],
                    "content_hash": evidence_text_hash(document["content"]),
                    "locator": json.dumps(
                        {
                            "source_type": document["source_type"] or "legacy_policy_source",
                            **({"source_checksum": document["source_checksum"]} if document["source_checksum"] else {}),
                        }
                    ),
                    "retention": datetime.now(UTC) + _RETENTION,
                },
            )
            for chunk in chunks:
                bind.execute(
                    sa.text(
                        "INSERT INTO policy_chunk_versions "
                        "(id, tenant_id, policy_document_version_id, scope_type, scope_id, doc_key, "
                        "document_version, chunk_id, chunk_version, content, text_hash, source_locator_json, "
                        "lifecycle_status, retention_until) VALUES (:id, :tenant_id, :document_version_id, "
                        "'tenant_policy', CAST(:tenant_id AS VARCHAR), :doc_key, :document_version, :chunk_id, 1, "
                        ":content, :text_hash, CAST(:locator AS jsonb), 'active', :retention)"
                    ),
                    {
                        "id": uuid4(),
                        "tenant_id": document["tenant_id"],
                        "document_version_id": document_version_id,
                        "doc_key": document["doc_key"],
                        "document_version": document["version"],
                        "chunk_id": chunk["chunk_id"],
                        "content": chunk["content"],
                        "text_hash": evidence_text_hash(chunk["content"]),
                        "locator": json.dumps(
                            {
                                "source_type": document["source_type"] or "legacy_policy_source",
                                "source_block_refs": list(chunk["source_block_refs_json"] or []),
                            }
                        ),
                        "retention": datetime.now(UTC) + _RETENTION,
                    },
                )
            resolved_count += 1
        else:
            binding_failure = _immutable_binding_failure(bind, document, chunks, existing)
            if binding_failure is not None:
                _mark_unresolved(bind, document, binding_failure)
                unresolved_count += 1
                continue
        bind.execute(
            sa.text(
                "UPDATE policy_documents SET evidence_write_sequence = COALESCE(evidence_write_sequence, :seq) WHERE id = :id"
            ),
            {"seq": watermark, "id": document["id"]},
        )
        bind.execute(
            sa.text(
                "UPDATE policy_chunks SET evidence_write_sequence = COALESCE(evidence_write_sequence, :seq) "
                "WHERE tenant_id = :tenant_id AND doc_id = :doc_id"
            ),
            {"seq": watermark, "tenant_id": document["tenant_id"], "doc_id": document["id"]},
        )
        canonical_count += 1
    return canonical_count, resolved_count, unresolved_count


def _legacy_failure(document: sa.RowMapping, chunks: list[sa.RowMapping]) -> str | None:
    fingerprint = document["policy_version_fingerprint"]
    if not fingerprint:
        return "missing_document_fingerprint"
    expected = build_policy_version_fingerprint(
        citation_text=document["content"],
        title=document["title"],
        doc_type=document["doc_type"],
        risk_level=document["risk_level"],
        effective_date=document["effective_date"],
    )
    if fingerprint != expected:
        return "document_fingerprint_mismatch"
    if not chunks:
        return "missing_chunks"
    chunk_ids = [str(chunk["chunk_id"]) for chunk in chunks]
    if len(chunk_ids) != len(set(chunk_ids)):
        return "ambiguous_logical_chunk"
    ordered_chunks = sorted(chunks, key=lambda chunk: (str(chunk["chunk_id"]), str(chunk["id"])))
    if "\n\n".join(str(chunk["content"]) for chunk in ordered_chunks).strip() != str(document["content"]).strip():
        return "document_chunk_content_mismatch"
    return None


def _immutable_binding_failure(
    bind: sa.Connection,
    document: sa.RowMapping,
    chunks: list[sa.RowMapping],
    document_versions: list[sa.RowMapping],
) -> str | None:
    if len(document_versions) != 1:
        return "missing_or_ambiguous_immutable_document"
    immutable_document = document_versions[0]
    if immutable_document["content_hash"] != evidence_text_hash(str(document["content"])):
        return "immutable_document_hash_mismatch"
    immutable_chunks = (
        bind.execute(
            sa.text(
                "SELECT chunk_id, text_hash FROM policy_chunk_versions "
                "WHERE tenant_id = :tenant_id AND policy_document_version_id = :document_version_id "
                "AND scope_type = 'tenant_policy' AND scope_id = CAST(:tenant_id AS VARCHAR)"
            ),
            {
                "tenant_id": document["tenant_id"],
                "document_version_id": immutable_document["id"],
            },
        )
        .mappings()
        .all()
    )
    expected = {(str(chunk["chunk_id"]), evidence_text_hash(str(chunk["content"]))) for chunk in chunks}
    actual = {(str(chunk["chunk_id"]), str(chunk["text_hash"])) for chunk in immutable_chunks}
    if len(expected) != len(chunks) or len(actual) != len(immutable_chunks) or expected != actual:
        return "immutable_chunk_binding_mismatch"
    return None


def _reconcile_current_heads(bind: sa.Connection, watermark: int) -> tuple[int, int, int]:
    """Perform the final exact-binding scan while the rollout lock is still held."""

    documents = bind.execute(
        sa.text(
            "SELECT id, tenant_id, doc_key, doc_type, title, effective_date, risk_level, version, content, "
            "policy_version_fingerprint, evidence_write_sequence FROM policy_documents "
            "ORDER BY tenant_id, doc_key, id FOR UPDATE"
        )
    ).mappings()
    canonical_count = 0
    unresolved_count = 0
    reconciled_through = watermark
    for document in documents:
        chunks = list(
            bind.execute(
                sa.text(
                    "SELECT id, chunk_id, content, evidence_write_sequence FROM policy_chunks "
                    "WHERE tenant_id = :tenant_id AND doc_id = :doc_id "
                    "ORDER BY tenant_id, doc_id, id FOR UPDATE"
                ),
                {"tenant_id": document["tenant_id"], "doc_id": document["id"]},
            ).mappings()
        )
        sequence = document["evidence_write_sequence"]
        failure = _legacy_failure(document, chunks)
        if sequence is None or any(chunk["evidence_write_sequence"] != sequence for chunk in chunks):
            failure = failure or "projection_sequence_mismatch"
        document_versions = (
            bind.execute(
                sa.text(
                    "SELECT id, content_hash FROM policy_document_versions WHERE tenant_id = :tenant_id "
                    "AND scope_type = 'tenant_policy' AND scope_id = CAST(:tenant_id AS VARCHAR) "
                    "AND doc_key = :doc_key AND document_version = :document_version"
                ),
                {
                    "tenant_id": document["tenant_id"],
                    "doc_key": document["doc_key"],
                    "document_version": document["version"],
                },
            )
            .mappings()
            .all()
        )
        failure = failure or _immutable_binding_failure(bind, document, chunks, document_versions)
        if failure is not None:
            _mark_unresolved(bind, document, failure)
            unresolved_count += 1
            continue
        canonical_count += 1
        reconciled_through = max(reconciled_through, int(sequence))
    return canonical_count, unresolved_count, reconciled_through


def _mark_unresolved(bind: sa.Connection, document: sa.RowMapping, reason: str) -> None:
    marker = json.dumps(
        {
            "evidence_identity_resolution": "legacy_unresolved",
            "evidence_identity_reason": reason,
        }
    )
    bind.execute(
        sa.text(
            "UPDATE policy_documents SET parser_metadata_json = COALESCE(parser_metadata_json, '{}'::jsonb) "
            "|| CAST(:marker AS jsonb) WHERE id = :id"
        ),
        {"marker": marker, "id": document["id"]},
    )
    bind.execute(
        sa.text(
            "UPDATE policy_chunks SET ocr_metadata_json = COALESCE(ocr_metadata_json, '{}'::jsonb) "
            "|| CAST(:marker AS jsonb) WHERE tenant_id = :tenant_id AND doc_id = :doc_id"
        ),
        {"marker": marker, "tenant_id": document["tenant_id"], "doc_id": document["id"]},
    )
