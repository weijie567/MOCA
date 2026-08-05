from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import CaseMemory
from src.knowledge.evidence_identity import (
    PersistedEvidenceIdentityMaterialV1,
    mint_canonical_evidence_identity,
)
from src.knowledge.schemas import EvidenceRefV1
from src.memory.case_memory import CaseMemoryRepository, CaseMemoryService
from src.memory.case_precedent import (
    ClosedCasePrecedentGenerationInput,
    _project_closed_case_candidate,
)
from src.memory.case_working_context_schemas import (
    CaseWorkingContextContentV1,
    CaseWorkingContextObservationV1,
)
from src.memory.fact_promotion import FactPromotionCandidateV1, promote_verified_fact
from src.memory.schemas import CaseMemoryProvenanceV1, CaseMemoryReviewDecision, MemorySourceRefV1
from src.tools.contracts import BusinessFactRefV1
from tests.memory.test_case_memory_provenance import _insert_run
from tests.replay.test_production_evidence_binding import (
    test_replay_resolves_retained_original_through_lifecycle_changes_and_blocks_purge as _assert_retained_replay,
)


_COVERAGE_GROUPS: dict[str, frozenset[str]] = {
    "promotion": frozenset(
        {
            "test_reviewed_memory_preserves_source_authority_through_lifecycle",
            "test_phase64_2_negative_authority_and_scope_matrix",
        }
    ),
    "identity": frozenset(
        {
            "test_phase64_2_exact_scope_serialization_storage_and_hash_material",
            "test_old_run_resolves_original_after_reingestion",
        }
    ),
    "replay": frozenset({"test_old_run_resolves_original_after_reingestion"}),
    "memory_identity": frozenset({"test_reviewed_memory_preserves_source_authority_through_lifecycle"}),
    "lifecycle": frozenset({"test_reviewed_memory_preserves_source_authority_through_lifecycle"}),
    "rollout": frozenset(
        {
            "test_ingestion_allocates_one_sequence_and_reuses_unchanged_binding",
            "test_unchanged_ingestions_on_both_sides_of_watermark_reconcile_by_binding_parity",
            "test_writer_and_cutover_share_rollout_lock_epoch",
            "test_operational_disable_waits_for_inflight_writer_and_keeps_dual_write",
        }
    ),
    "approval": frozenset(
        {
            "test_create_persists_one_repository_canonical_evidence_list",
            "test_edit_changed_evidence_uses_one_repository_canonical_binding",
            "test_attach_info_changed_evidence_uses_one_repository_canonical_binding",
        }
    ),
    "append": frozenset(
        {
            "test_new_append_rejects_legacy_raw_input_and_mixed_forged_refs_atomically",
            "test_investigate_event_replays_exact_original_evidence",
        }
    ),
    "provenance": frozenset(
        {
            "test_resolved_and_legacy_unresolved_provenance_cannot_impersonate_each_other",
            "test_rejected_cwc_observation_never_enters_case_memory",
            "test_migration_backfills_exact_claims_and_survivor_to_many_lineage",
        }
    ),
    "claims": frozenset(
        {
            "test_delayed_exact_submit_cannot_revive_terminal_claim",
            "test_equal_content_with_distinct_source_identity_is_not_idempotent",
            "test_review_cas_is_single_winner_and_exact_retry_reuses_event",
        }
    ),
}


def build_integrity_coverage_matrix() -> dict[str, frozenset[str]]:
    """Map every locked requirement/threat/review finding to executable tests."""

    groups = {
        "SC-64.2-1": ("promotion", "provenance"),
        "SC-64.2-2": ("identity", "approval", "append"),
        "SC-64.2-3": ("identity", "replay", "rollout"),
        "SC-64.2-4": ("memory_identity", "provenance", "claims"),
        "SC-64.2-5": ("claims",),
        "T64.2-01": ("identity", "approval"),
        "T64.2-02": ("replay", "append"),
        "T64.2-03": ("identity", "provenance"),
        "T64.2-04": ("memory_identity",),
        "T64.2-05": ("claims",),
        "T64.2-06": ("claims",),
        "T64.2-07": ("promotion", "provenance"),
        "T64.2-08": ("identity", "approval", "replay", "provenance"),
        "CLAUDE-01": ("identity", "approval", "append"),
        "CLAUDE-02": ("append", "replay"),
        "CLAUDE-03": ("rollout",),
        "CLAUDE-04": ("replay", "rollout"),
        "CLAUDE-05": ("provenance",),
        "CLAUDE-06": ("promotion",),
        "CLAUDE-07": ("claims",),
        "CLAUDE-08": ("provenance", "claims"),
        "CLAUDE-09": ("provenance", "claims"),
        "CLAUDE-10": ("rollout", "replay"),
        "CLAUDE-11": ("identity", "memory_identity", "replay"),
        "CLAUDE-12": ("identity", "rollout"),
        "CLAUDE-R2-01": ("rollout",),
        "CLAUDE-R2-02": ("rollout", "append"),
        "CLAUDE-R2-03": ("approval", "provenance"),
        "CLAUDE-R2-04": ("claims", "replay"),
    }
    return {
        requirement: frozenset().union(*(_COVERAGE_GROUPS[group] for group in group_names))
        for requirement, group_names in groups.items()
    }


def _canonical_policy_ref(tenant_id: uuid.UUID, *, observed_at: datetime) -> EvidenceRefV1:
    material = PersistedEvidenceIdentityMaterialV1(
        tenant_id=str(tenant_id),
        scope_type="tenant_policy",
        scope_id=str(tenant_id),
        document_version_id=str(uuid.uuid4()),
        chunk_version_id=str(uuid.uuid4()),
        doc_key="phase64-2-integration-policy",
        document_version=2,
        chunk_id="phase64-2-integration-policy#1",
        chunk_version=1,
        text_hash=f"sha256:{'a' * 64}",
    )
    result = mint_canonical_evidence_identity(
        material,
        expected_tenant_id=str(tenant_id),
        expected_scope_type="tenant_policy",
        expected_scope_id=str(tenant_id),
    )
    assert result.identity is not None
    return EvidenceRefV1.from_canonical_identity(
        result.identity,
        retrieved_at=observed_at.isoformat(),
        retrieval_config_version="retrieval.v3",
        rank=1,
    )


def test_phase64_2_matrix_maps_every_locked_requirement() -> None:
    matrix = build_integrity_coverage_matrix()

    assert set(matrix) == {
        *(f"SC-64.2-{index}" for index in range(1, 6)),
        *(f"T64.2-{index:02d}" for index in range(1, 9)),
        *(f"CLAUDE-{index:02d}" for index in range(1, 13)),
        *(f"CLAUDE-R2-{index:02d}" for index in range(1, 5)),
    }
    assert all(test_names for test_names in matrix.values())


def test_phase64_2_exact_scope_serialization_storage_and_hash_material() -> None:
    tenant_id = uuid.uuid4()
    ref = _canonical_policy_ref(tenant_id, observed_at=datetime(2026, 8, 5, 12, 0, tzinfo=UTC))
    identity = ref.to_canonical_identity()

    assert identity is not None
    assert ref.model_dump(mode="json")["scope_type"] == "tenant_policy"
    assert ref.model_dump(mode="json")["scope_id"] == str(tenant_id)
    assert identity.hash_material()["scope_type"] == "tenant_policy"
    assert identity.hash_material()["scope_id"] == str(tenant_id)
    assert ref.evidence_id == identity.evidence_id


@pytest.mark.asyncio
async def test_old_run_resolves_original_after_reingestion(
    session: AsyncSession,
    seeded_session: dict,
) -> None:
    """Key link: canonical retrieval/emitter binding retains the old replay bytes."""

    await _assert_retained_replay(
        session,
        seeded_session,
    )


@pytest.mark.asyncio
async def test_reviewed_memory_preserves_source_authority_through_lifecycle(
    session: AsyncSession,
    seeded_session: dict,
) -> None:
    """Key link: typed observation promotion survives review and terminal lifecycle."""

    tenant_id = seeded_session["tenant"].id
    case_id = seeded_session["refund_case"].id
    run_id = await _insert_run(session, seeded_session, thread_id="phase64-2-integrity-memory")
    observed_at = datetime(2026, 8, 5, 12, 0, tzinfo=UTC)
    business_ref = BusinessFactRefV1(
        tenant_id=str(tenant_id),
        source_system="refund_service",
        resource_type="refund_case",
        resource_id=str(case_id),
        resource_version="v9",
        data_freshness_at=observed_at,
        retrieved_at=observed_at,
    )
    evidence_ref = _canonical_policy_ref(tenant_id, observed_at=observed_at)
    source_ref = MemorySourceRefV1(
        source_type="run_auto_terminal",
        run_id=str(run_id),
        agent_run_id=str(run_id),
        event_id="phase64-2-integrity-close",
        business_object_type="refund_case",
        business_object_id=str(case_id),
    )
    business = promote_verified_fact(
        FactPromotionCandidateV1(
            tenant_id=str(tenant_id),
            summary="Refund case is closed.",
            authority_class="business_fact",
            status="success",
            completeness="complete",
            scope_result="valid",
            freshness_result="valid",
            reference_validation="valid",
            observed_at=observed_at,
            business_fact_refs=[business_ref],
        )
    )
    policy = promote_verified_fact(
        FactPromotionCandidateV1(
            tenant_id=str(tenant_id),
            summary="Canonical policy evidence applies.",
            authority_class="policy_evidence",
            status="success",
            completeness="complete",
            scope_result="valid",
            freshness_result="valid",
            reference_validation="valid",
            observed_at=observed_at,
            policy_evidence_refs=[evidence_ref],
        )
    )
    rejected_marker = "REJECTED-PHASE64-2-INTEGRATION-OBSERVATION"
    content = CaseWorkingContextContentV1(
        issue_type="refund_dispute",
        verified_facts=[
            business.to_verified_fact(source_ref=source_ref),
            policy.to_verified_fact(source_ref=source_ref),
        ],
        evidence_refs=[
            CaseWorkingContextObservationV1(
                summary=rejected_marker,
                decision="reject",
                authority_class="unknown",
                status="error",
                reason_code="unknown_authority",
                completeness="partial",
                scope_result="unknown",
                freshness_result="unknown",
                reference_validation="invalid",
                source_ref=source_ref,
                observed_at=observed_at,
            )
        ],
    )
    candidate = _project_closed_case_candidate(
        request=ClosedCasePrecedentGenerationInput(
            tenant_id=tenant_id,
            case_id=case_id,
            run_id=run_id,
            closed_status="closed",
            close_event_id="phase64-2-integrity-close",
            closed_at=observed_at,
        ),
        content=content,
        cwc_row=SimpleNamespace(id=uuid.uuid4(), version=4, pii_classification="none"),
        scope_type="case",
        scope_id=str(case_id),
    )
    service = CaseMemoryService(CaseMemoryRepository(session))
    written = await service.submit_case_memory_candidate(candidate, now=observed_at)
    assert written.memory_id is not None
    row = await session.get(CaseMemory, written.memory_id)
    assert row is not None
    before = CaseMemoryProvenanceV1.model_validate(row.provenance_json)
    reviewer = seeded_session["users"]["admin_user"]

    await service.approve_case_memory(
        CaseMemoryReviewDecision(
            tenant_id=tenant_id,
            run_id=run_id,
            case_memory_id=row.id,
            reviewer_user_id=reviewer.id,
            expected_lifecycle_version=1,
            reason_code="approved",
            review_reason="source authority verified",
        ),
        now=observed_at,
    )
    await service.delete_case_memory(
        tenant_id=tenant_id,
        case_memory_id=row.id,
        run_id=run_id,
        expected_lifecycle_version=2,
        reason_code="integrity_closeout",
        now=observed_at,
    )
    await session.refresh(row)
    after = CaseMemoryProvenanceV1.model_validate(row.provenance_json)

    assert [item.source_authority_class for item in after.source_authorities] == [
        "business_fact",
        "policy_evidence",
    ]
    assert after.source_authorities == before.source_authorities
    assert after.memory_authority_class == "contextual_only"
    assert row.review_status == "deleted" and row.lifecycle_version == 3
    assert rejected_marker not in str(row.provenance_json)


def test_phase64_2_negative_authority_and_scope_matrix() -> None:
    tenant_id = uuid.uuid4()
    observed_at = datetime(2026, 8, 5, 12, 0, tzinfo=UTC)
    business_ref = BusinessFactRefV1(
        tenant_id=str(tenant_id),
        source_system="refund_service",
        resource_type="refund_case",
        resource_id="RF-NEGATIVE",
        resource_version="v1",
        data_freshness_at=observed_at,
        retrieved_at=observed_at,
    )
    for authority, expected in (("contextual_only", "observe"), ("unknown", "reject")):
        result = promote_verified_fact(
            FactPromotionCandidateV1(
                tenant_id=str(tenant_id),
                summary="must remain non-authoritative",
                authority_class=authority,
                status="success",
                completeness="complete",
                scope_result="valid",
                freshness_result="valid",
                reference_validation="valid",
                observed_at=observed_at,
                business_fact_refs=[business_ref],
            )
        )
        assert result.decision == expected

    for status in (
        "denied",
        "unavailable",
        "stale",
        "malformed",
        "partial",
        "partial_success",
        "timeout",
        "error",
        "invalid_request",
        "invalid_response",
        "not_found",
        "legacy_unresolved",
        "conflict",
    ):
        result = promote_verified_fact(
            FactPromotionCandidateV1(
                tenant_id=str(tenant_id),
                summary=status,
                authority_class="business_fact",
                status=status,
                completeness="complete",
                scope_result="valid",
                freshness_result="valid",
                reference_validation="valid",
                observed_at=observed_at,
                business_fact_refs=[business_ref],
            )
        )
        assert result.decision != "promote"
