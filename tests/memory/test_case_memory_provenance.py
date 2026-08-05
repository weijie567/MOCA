from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
from types import SimpleNamespace
import uuid

import pytest
from pydantic import TypeAdapter, ValidationError
from sqlalchemy import CheckConstraint, ForeignKeyConstraint, UniqueConstraint

from src.db.models import Base, CaseMemory, CaseMemoryLineageLink
from src.knowledge.evidence_identity import (
    PersistedEvidenceIdentityMaterialV1,
    mint_canonical_evidence_identity,
)
from src.knowledge.schemas import EvidenceRefV1
from src.memory.case_memory import CaseMemoryService
from src.memory.case_precedent import (
    ClosedCasePrecedentGenerationInput,
    _project_closed_case_candidate,
)
from src.memory.case_working_context_schemas import (
    CaseWorkingContextContentV1,
    CaseWorkingContextObservationV1,
    CaseWorkingContextVerifiedFactV1,
)
from src.memory.schemas import (
    CaseMemoryProvenanceEnvelope,
    CaseMemoryProvenanceV1,
    CaseMemorySourceAuthorityV1,
    LegacyUnresolvedCaseMemoryProvenanceV1,
    MemorySourceRefV1,
)
from src.tools.contracts import BusinessFactRefV1


MIGRATION_PATH = Path("src/db/migrations/versions/027_phase64_2_memory_provenance.py")
_HASH_A = f"sha256:{'a' * 64}"
_HASH_B = f"sha256:{'b' * 64}"
_HASH_C = f"sha256:{'c' * 64}"


def _source_ref(*, case_id: uuid.UUID, run_id: uuid.UUID, tool_result_id: str) -> MemorySourceRefV1:
    return MemorySourceRefV1(
        source_type="run_auto_terminal",
        run_id=str(run_id),
        agent_run_id=str(run_id),
        tool_result_id=tool_result_id,
        business_object_type="refund_case",
        business_object_id=str(case_id),
    )


def _business_ref(*, tenant_id: uuid.UUID, case_id: uuid.UUID) -> BusinessFactRefV1:
    observed_at = datetime(2026, 8, 5, 9, 0, tzinfo=UTC)
    return BusinessFactRefV1(
        tenant_id=str(tenant_id),
        source_system="refund_service",
        resource_type="refund_case",
        resource_id=str(case_id),
        resource_version="v7",
        data_freshness_at=observed_at,
        retrieved_at=observed_at,
    )


def _evidence_ref(*, tenant_id: uuid.UUID) -> EvidenceRefV1:
    material = PersistedEvidenceIdentityMaterialV1(
        tenant_id=str(tenant_id),
        scope_type="tenant_policy",
        scope_id=str(tenant_id),
        document_version_id="10000000-0000-0000-0000-000000000001",
        chunk_version_id="20000000-0000-0000-0000-000000000002",
        doc_key="refund_policy",
        document_version=4,
        chunk_id="refund_policy#damage",
        chunk_version=2,
        text_hash=_HASH_A,
    )
    resolution = mint_canonical_evidence_identity(
        material,
        expected_tenant_id=str(tenant_id),
        expected_scope_type="tenant_policy",
        expected_scope_id=str(tenant_id),
    )
    assert resolution.identity is not None
    return EvidenceRefV1.from_canonical_identity(
        resolution.identity,
        retrieved_at="2026-08-05T09:00:00Z",
        retrieval_config_version="retrieval.v3",
        rank=1,
    )


def _resolved_provenance(
    *,
    tenant_id: uuid.UUID,
    case_id: uuid.UUID,
    run_id: uuid.UUID,
    cwc_id: uuid.UUID,
    candidate_hash: str = _HASH_A,
    content_hash: str = _HASH_B,
    source_identity_hash: str = _HASH_C,
) -> CaseMemoryProvenanceV1:
    business_ref = _business_ref(tenant_id=tenant_id, case_id=case_id)
    evidence_ref = _evidence_ref(tenant_id=tenant_id)
    business_source = _source_ref(case_id=case_id, run_id=run_id, tool_result_id="tool-business")
    policy_source = _source_ref(case_id=case_id, run_id=run_id, tool_result_id="tool-policy")
    return CaseMemoryProvenanceV1(
        tenant_id=tenant_id,
        scope_type="case",
        scope_id=str(case_id),
        resolution_status="canonical",
        memory_authority_class="contextual_only",
        source_authorities=[
            CaseMemorySourceAuthorityV1(
                source_kind="business_fact",
                source_ref=business_source,
                source_status="success",
                source_authority_class="business_fact",
                business_fact_refs=[business_ref],
            ),
            CaseMemorySourceAuthorityV1(
                source_kind="policy_evidence",
                source_ref=policy_source,
                source_status="success",
                source_authority_class="policy_evidence",
                evidence_refs=[evidence_ref],
            ),
        ],
        source_run_id=run_id,
        source_event_id=f"refund-case-close:{case_id}:close-1",
        source_cwc_id=cwc_id,
        source_cwc_revision=3,
        evidence_refs=[evidence_ref],
        business_fact_refs=[business_ref],
        identity_algorithm_version="memory_identity.v1",
        identity_profile="nfc_selective_v2",
        candidate_hash=candidate_hash,
        content_hash=content_hash,
        source_identity_hash=source_identity_hash,
    )


def test_resolved_and_legacy_unresolved_provenance_cannot_impersonate_each_other() -> None:
    tenant_id = uuid.uuid4()
    case_id = uuid.uuid4()
    run_id = uuid.uuid4()
    cwc_id = uuid.uuid4()
    resolved = _resolved_provenance(
        tenant_id=tenant_id,
        case_id=case_id,
        run_id=run_id,
        cwc_id=cwc_id,
    )
    unresolved = LegacyUnresolvedCaseMemoryProvenanceV1(
        tenant_id=tenant_id,
        case_memory_id=uuid.uuid4(),
        legacy_content_hash=_HASH_A,
        legacy_source_identity_hash=None,
        legacy_source_ref={"source_type": "legacy", "event_id": "literal-event"},
        legacy_policy_refs=[{"doc_key": "literal-policy"}],
        unresolved_reasons=["pre_027_provenance_unavailable"],
    )
    adapter = TypeAdapter(CaseMemoryProvenanceEnvelope)

    assert isinstance(adapter.validate_python(resolved.model_dump(mode="json")), CaseMemoryProvenanceV1)
    assert isinstance(
        adapter.validate_python(unresolved.model_dump(mode="json")),
        LegacyUnresolvedCaseMemoryProvenanceV1,
    )
    unresolved_impersonation = unresolved.model_dump(mode="json") | {
        "scope_type": "case",
        "scope_id": str(case_id),
        "memory_authority_class": "contextual_only",
        "candidate_hash": _HASH_B,
    }
    with pytest.raises(ValidationError):
        adapter.validate_python(unresolved_impersonation)
    resolved_impersonation = resolved.model_dump(mode="json") | {
        "schema_version": "case_memory_provenance_legacy_unresolved.v1",
        "resolution_status": "legacy_unresolved",
    }
    with pytest.raises(ValidationError):
        adapter.validate_python(resolved_impersonation)


def test_source_authority_rejects_contextual_unknown_and_incomplete_policy_refs() -> None:
    tenant_id = uuid.uuid4()
    case_id = uuid.uuid4()
    run_id = uuid.uuid4()
    source_ref = _source_ref(case_id=case_id, run_id=run_id, tool_result_id="tool-1")

    for invalid_authority in ("contextual_only", "unknown"):
        with pytest.raises(ValidationError):
            CaseMemorySourceAuthorityV1(
                source_kind="business_fact",
                source_ref=source_ref,
                source_status="success",
                source_authority_class=invalid_authority,
                business_fact_refs=[_business_ref(tenant_id=tenant_id, case_id=case_id)],
            )
    with pytest.raises(ValidationError):
        CaseMemorySourceAuthorityV1(
            source_kind="policy_evidence",
            source_ref=source_ref,
            source_status="success",
            source_authority_class="policy_evidence",
            evidence_refs=[
                EvidenceRefV1.build(
                    tenant_id=str(tenant_id),
                    doc_key="legacy",
                    chunk_id="legacy#1",
                    policy_version="v1",
                    text="legacy",
                    retrieved_at="2026-08-05T09:00:00Z",
                    retrieval_config_version="retrieval.v3",
                )
            ],
        )


def test_rejected_cwc_observation_never_enters_case_memory() -> None:
    tenant_id = uuid.uuid4()
    case_id = uuid.uuid4()
    run_id = uuid.uuid4()
    cwc_id = uuid.uuid4()
    observed_at = datetime(2026, 8, 5, 9, 0, tzinfo=UTC)
    forbidden = "REJECTED-CWC-OBSERVATION-MUST-STAY-AUDIT-ONLY"
    business_ref = _business_ref(tenant_id=tenant_id, case_id=case_id)
    evidence_ref = _evidence_ref(tenant_id=tenant_id)
    content = CaseWorkingContextContentV1(
        issue_type="refund_dispute",
        verified_facts=[
            CaseWorkingContextVerifiedFactV1(
                text="Refund case status is closed.",
                authority_class="business_fact",
                status="success",
                promotion_reason_code="authoritative_business_fact",
                source_ref=_source_ref(case_id=case_id, run_id=run_id, tool_result_id="tool-business"),
                observed_at=observed_at,
                business_fact_refs=[business_ref],
            ),
            CaseWorkingContextVerifiedFactV1(
                text="Canonical refund policy evidence was verified.",
                authority_class="policy_evidence",
                status="success",
                promotion_reason_code="authoritative_policy_evidence",
                source_ref=_source_ref(case_id=case_id, run_id=run_id, tool_result_id="tool-policy"),
                observed_at=observed_at,
                policy_evidence_refs=[evidence_ref],
            ),
        ],
        evidence_refs=[
            CaseWorkingContextObservationV1(
                summary=forbidden,
                decision="reject",
                authority_class="unknown",
                status="error",
                reason_code="unknown_authority",
                completeness="partial",
                scope_result="unknown",
                freshness_result="unknown",
                reference_validation="missing",
                source_ref=_source_ref(case_id=case_id, run_id=run_id, tool_result_id="tool-rejected"),
                observed_at=observed_at,
            )
        ],
        # Even if a stale caller duplicates a rejected ref in the aggregate CWC field,
        # projection must derive policy refs exclusively from promoted facts.
        policy_refs=[evidence_ref],
    )
    candidate = _project_closed_case_candidate(
        request=ClosedCasePrecedentGenerationInput(
            tenant_id=tenant_id,
            case_id=case_id,
            run_id=run_id,
            closed_status="closed",
            close_event_id="close-1",
            closed_at=observed_at,
        ),
        content=content,
        cwc_row=SimpleNamespace(id=cwc_id, version=3, pii_classification="none"),
        scope_type="case",
        scope_id=str(case_id),
    )

    rendered = json.dumps(candidate.model_dump(mode="json"), ensure_ascii=False, sort_keys=True)
    assert forbidden not in rendered
    assert candidate.policy_refs == [evidence_ref.model_dump(mode="json")]
    assert candidate.provenance is not None
    assert candidate.provenance.memory_authority_class == "contextual_only"
    assert [item.source_authority_class for item in candidate.provenance.source_authorities] == [
        "business_fact",
        "policy_evidence",
    ]
    assert candidate.provenance.business_fact_refs == [business_ref]
    assert candidate.provenance.evidence_refs == [evidence_ref]


class _CapturingRepository:
    def __init__(self) -> None:
        self.insert_kwargs: dict = {}

    async def check_tombstone_before_write(self, **kwargs):
        return None

    async def get_active_duplicate(self, **kwargs):
        return None

    async def insert_case_memory(self, candidate, **kwargs):
        self.insert_kwargs = kwargs
        return SimpleNamespace(id=uuid.uuid4(), review_status=kwargs["review_status"])

    async def emit_write_event(self, **kwargs):
        return SimpleNamespace(id=uuid.uuid4())


@pytest.mark.asyncio
async def test_service_persists_validated_canonical_provenance_atomically() -> None:
    tenant_id = uuid.uuid4()
    case_id = uuid.uuid4()
    run_id = uuid.uuid4()
    observed_at = datetime(2026, 8, 5, 9, 0, tzinfo=UTC)
    content = CaseWorkingContextContentV1(
        issue_type="refund_dispute",
        verified_facts=[
            CaseWorkingContextVerifiedFactV1(
                text="Refund is closed.",
                authority_class="business_fact",
                status="success",
                promotion_reason_code="authoritative_business_fact",
                source_ref=_source_ref(case_id=case_id, run_id=run_id, tool_result_id="tool-business"),
                observed_at=observed_at,
                business_fact_refs=[_business_ref(tenant_id=tenant_id, case_id=case_id)],
            )
        ],
    )
    candidate = _project_closed_case_candidate(
        request=ClosedCasePrecedentGenerationInput(
            tenant_id=tenant_id,
            case_id=case_id,
            run_id=run_id,
            closed_status="closed",
            close_event_id="close-persist",
            closed_at=observed_at,
        ),
        content=content,
        cwc_row=SimpleNamespace(id=uuid.uuid4(), version=4, pii_classification="none"),
        scope_type="case",
        scope_id=str(case_id),
    )
    repository = _CapturingRepository()

    result = await CaseMemoryService(repository).submit_case_memory_candidate(candidate, now=observed_at)

    persisted = CaseMemoryProvenanceV1.model_validate(repository.insert_kwargs["provenance_json"])
    assert result.status == "needs_review"
    assert persisted.tenant_id == tenant_id
    assert persisted.scope_type == "case"
    assert persisted.scope_id == str(case_id)
    assert persisted.candidate_hash == result.candidate_hash
    assert persisted.content_hash == result.content_hash
    assert persisted.source_identity_hash == result.source_identity_hash
    assert repository.insert_kwargs["identity_algorithm_version"] == "memory_identity.v1"
    assert repository.insert_kwargs["candidate_hash"] == result.candidate_hash
    assert repository.insert_kwargs["identity_resolution_status"] == "canonical"
    assert repository.insert_kwargs["lifecycle_version"] == 1


def test_orm_and_migration_define_provenance_and_survivor_to_many_lineage() -> None:
    source = MIGRATION_PATH.read_text(encoding="utf-8")
    case_columns = set(CaseMemory.__table__.c.keys())
    assert {
        "identity_algorithm_version",
        "candidate_hash",
        "identity_resolution_status",
        "provenance_json",
        "lifecycle_version",
        "corrects_case_memory_id",
        "supersedes_case_memory_id",
    } <= case_columns
    assert "case_memory_lineage_links" in Base.metadata.tables
    assert CaseMemoryLineageLink.__tablename__ == "case_memory_lineage_links"

    constraints = [*CaseMemoryLineageLink.__table__.constraints]
    assert any(
        isinstance(item, UniqueConstraint)
        and {column.name for column in item.columns}
        == {"tenant_id", "survivor_case_memory_id", "related_case_memory_id", "relation"}
        for item in constraints
    )
    assert any(
        isinstance(item, CheckConstraint) and "survivor_case_memory_id <> related_case_memory_id" in str(item.sqltext)
        for item in constraints
    )
    lineage_fks = [item for item in constraints if isinstance(item, ForeignKeyConstraint)]
    assert len(lineage_fks) >= 3
    assert all(element.ondelete == "RESTRICT" for item in lineage_fks for element in item.elements)

    assert 'revision: str = "027_phase64_2_memory_provenance"' in source
    assert 'down_revision: str | None = "026_phase64_2_evidence_cutover"' in source
    assert "case_memory_provenance_legacy_unresolved.v1" in source
    assert "pre_027_provenance_unavailable" in source
    assert "case_memory_lineage_links" in source
    assert "provenance_json" in source
    assert "_assert_downgrade_safe" in source
