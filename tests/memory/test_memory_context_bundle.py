from __future__ import annotations

import pytest

from src.memory.context_refs import ReviewedMemoryContextBundle, ReviewedMemoryContextRetrieveStatusV1
from src.memory.context_service import MemoryContextService
from src.memory.schemas import SessionContextMemory, SessionMemoryView


def _session_context() -> SessionContextMemory:
    return SessionContextMemory(
        tenant_id="tenant-1",
        user_id="user-1",
        thread_id="thread-1",
        run_id="run-1",
        slot_continuity=SessionMemoryView(
            source="postgres_session_memory",
            continuity_claimed=True,
            active_slots={"order_id": "ORD-1001"},
            slot_metadata={"order_id": {"source": "trusted_session_memory"}},
        ),
        policy_topic_hints=["refund_timeout"],
        prior_policy_mention_refs=[{"doc_key": "refund_policy", "chunk_id": "chunk-1"}],
    )


@pytest.mark.asyncio
async def test_memory_context_service_projects_agent_facing_bundle_without_merging_authority() -> None:
    reviewed = ReviewedMemoryContextBundle(
        long_term_items=[{"memory_id": "ltm-1", "content": "Merchant prefers concise summaries."}],
        case_items=[{"case_memory_id": "case-1", "excerpt": "Reviewed precedent excerpt."}],
        status_ref=ReviewedMemoryContextRetrieveStatusV1(
            status="loaded",
            retrieved_refs=[],
            filter_reasons=["reviewed_prompt_safe"],
        ),
    )

    bundle = await MemoryContextService().load_memory_bundle_after_slot_resolution(
        session_context=_session_context(),
        reviewed_memory_context=reviewed,
    )

    assert bundle.schema_version == "memory_context_bundle.v1"
    assert bundle.authority_class == "contextual_only"
    assert bundle.session_context.slot_continuity.active_slots == {"order_id": "ORD-1001"}
    assert bundle.session_context.policy_topic_hints == ["refund_timeout"]
    assert bundle.session_context.prior_policy_mention_refs == [{"doc_key": "refund_policy", "chunk_id": "chunk-1"}]
    assert bundle.long_term_items == reviewed.long_term_items
    assert bundle.case_items == reviewed.case_items
    assert bundle.reviewed_status_ref == reviewed.status_ref
