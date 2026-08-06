from __future__ import annotations

import inspect
import re
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from src.memory.identity import (
    LEGACY_MEMORY_IDENTITY_PROFILE,
    MEMORY_IDENTITY_PROFILE,
    MemoryCandidateIdentityV1,
    MemoryIdentityError,
    build_case_memory_candidate_identity,
    build_case_working_context_candidate_identity,
    build_long_term_memory_candidate_identity,
    build_session_memory_candidate_identity,
    canonical_memory_candidate_hash,
    canonical_memory_content_hash,
    canonical_memory_identity_hash,
    canonical_source_identity_hash,
    normalize_memory_content,
)
from src.memory.case_working_context_schemas import (
    CaseWorkingContextContentV1,
    CaseWorkingContextWriteCandidate,
)
from src.memory.schemas import (
    CaseMemoryWriteCandidate,
    LongTermMemoryWriteCandidate,
    MemoryIdentityV1,
    MemorySourceRefV1,
    SessionMemoryWriteCandidate,
    SessionSlotV1,
)
from src.memory.service import MemoryService


SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
SOURCE_REF_KEYS = {
    "source_type",
    "run_id",
    "event_id",
    "conversation_message_id",
    "tool_result_id",
    "agent_run_id",
    "business_object_type",
    "business_object_id",
    "policy_version",
    "outcome_id",
}
RAW_AUTHORITY_FIELDS = {
    "raw_payload",
    "raw_tool_output",
    "full_policy_text",
    "policy_evidence",
    "approval_authority_body",
    "action_authority_body",
    "replay_blob",
    "debug_blob",
}


def _source_ref(**overrides: str) -> dict[str, str]:
    source_ref = {
        "source_type": "conversation_message",
        "run_id": "run-1",
        "event_id": "event-1",
        "conversation_message_id": "msg-1",
        "tool_result_id": "tool-result-1",
        "agent_run_id": "agent-run-1",
        "business_object_type": "refund",
        "business_object_id": "RF-1001",
        "policy_version": "v3",
        "outcome_id": "outcome-1",
    }
    source_ref.update(overrides)
    return source_ref


def test_memory_content_hash_is_stable_across_whitespace() -> None:
    assert normalize_memory_content(
        "  Refund  policy\npreference  ",
        identity_profile=LEGACY_MEMORY_IDENTITY_PROFILE,
    ) == "refund policy preference"

    content_hash = canonical_memory_content_hash(
        memory_type="long_term_fact",
        content="Refund policy preference",
    )

    assert SHA256_RE.fullmatch(content_hash)
    assert content_hash == canonical_memory_content_hash(
        memory_type="long_term_fact",
        content="  Refund  policy\npreference  ",
    )
    assert content_hash != canonical_memory_content_hash(
        memory_type="case_memory",
        content="Refund policy preference",
    )


def test_memory_identity_hash_binds_scope_and_content() -> None:
    content_hash = canonical_memory_content_hash(
        memory_type="long_term_fact",
        content="Refund policy preference",
    )

    identity_hash = canonical_memory_identity_hash(
        tenant_id="tenant-1",
        memory_type="long_term_fact",
        scope_type="merchant",
        scope_id="merchant-1",
        content_hash=content_hash,
    )

    assert SHA256_RE.fullmatch(identity_hash)
    assert identity_hash == canonical_memory_identity_hash(
        tenant_id="tenant-1",
        memory_type="long_term_fact",
        scope_type="merchant",
        scope_id="merchant-1",
        content_hash=content_hash,
    )
    assert identity_hash != canonical_memory_identity_hash(
        tenant_id="tenant-2",
        memory_type="long_term_fact",
        scope_type="merchant",
        scope_id="merchant-1",
        content_hash=content_hash,
    )


def test_memory_candidate_hash_binds_scope_content_and_source_identity() -> None:
    content_hash = canonical_memory_content_hash(
        memory_type="long_term_fact",
        content="Refund policy preference",
    )
    source_identity_hash = canonical_source_identity_hash(_source_ref())

    candidate_hash = canonical_memory_candidate_hash(
        tenant_id="tenant-1",
        memory_type="long_term_fact",
        scope_type="merchant",
        scope_id="merchant-1",
        content_hash=content_hash,
        source_identity_hash=source_identity_hash,
    )

    assert SHA256_RE.fullmatch(candidate_hash)
    assert candidate_hash == canonical_memory_candidate_hash(
        tenant_id="tenant-1",
        memory_type="long_term_fact",
        scope_type="merchant",
        scope_id="merchant-1",
        content_hash=content_hash,
        source_identity_hash=source_identity_hash,
    )

    base_candidate = {
        "tenant_id": "tenant-1",
        "memory_type": "long_term_fact",
        "scope_type": "merchant",
        "scope_id": "merchant-1",
        "content_hash": content_hash,
        "source_identity_hash": source_identity_hash,
    }
    variations = [
        {"tenant_id": "tenant-2"},
        {"memory_type": "case_memory"},
        {"scope_type": "user"},
        {"scope_id": "merchant-2"},
        {"content_hash": canonical_memory_content_hash(memory_type="long_term_fact", content="Other")},
        {"source_identity_hash": canonical_source_identity_hash(_source_ref(event_id="event-2"))},
    ]

    for variation in variations:
        changed_candidate = base_candidate | variation
        assert candidate_hash != canonical_memory_candidate_hash(**changed_candidate)


def test_memory_candidate_hash_accepts_only_stable_envelope_fields() -> None:
    parameters = set(inspect.signature(canonical_memory_candidate_hash).parameters)

    assert parameters == {
        "tenant_id",
        "memory_type",
        "scope_type",
        "scope_id",
        "content_hash",
        "source_identity_hash",
    }
    assert parameters.isdisjoint(RAW_AUTHORITY_FIELDS)

    with pytest.raises(TypeError):
        canonical_memory_candidate_hash(
            tenant_id="tenant-1",
            memory_type="long_term_fact",
            scope_type="merchant",
            scope_id="merchant-1",
            content_hash="sha256:" + "a" * 64,
            source_identity_hash=None,
            raw_payload={"tool": "result"},
        )


def test_source_identity_hash_accepts_only_memory_source_ref_keys() -> None:
    source_identity_hash = canonical_source_identity_hash(_source_ref())

    assert SHA256_RE.fullmatch(source_identity_hash)
    assert source_identity_hash == canonical_source_identity_hash(dict(reversed(_source_ref().items())))
    assert source_identity_hash != canonical_source_identity_hash(_source_ref(event_id="event-2"))
    assert SOURCE_REF_KEYS == set(_source_ref())


def test_source_identity_hash_requires_durable_discriminator() -> None:
    assert canonical_source_identity_hash({"source_type": "deterministic_tool_result"}) is None
    assert canonical_source_identity_hash({"source_type": "deterministic_tool_result", "run_id": "run-1"}) is None
    assert SHA256_RE.fullmatch(
        canonical_source_identity_hash({"source_type": "deterministic_tool_result", "event_id": "event-1"})
    )


def test_source_identity_rejects_unknown_keys() -> None:
    with pytest.raises(MemoryIdentityError, match="unknown"):
        canonical_source_identity_hash({"random_json_key": "x"})


def test_memory_identity_schemas_are_prompt_safe() -> None:
    content_hash = canonical_memory_content_hash(
        memory_type="long_term_fact",
        content="Refund policy preference",
    )
    source_identity_hash = canonical_source_identity_hash(_source_ref())
    candidate_hash = canonical_memory_candidate_hash(
        tenant_id="tenant-1",
        memory_type="long_term_fact",
        scope_type="merchant",
        scope_id="merchant-1",
        content_hash=content_hash,
        source_identity_hash=source_identity_hash,
    )

    assert set(MemorySourceRefV1.model_fields) == SOURCE_REF_KEYS
    assert set(MemorySourceRefV1.model_fields).isdisjoint(RAW_AUTHORITY_FIELDS)
    assert set(MemoryIdentityV1.model_fields).isdisjoint(RAW_AUTHORITY_FIELDS)
    assert set(MemoryCandidateIdentityV1.model_fields).isdisjoint(RAW_AUTHORITY_FIELDS)
    assert "candidate_hash" in MemoryCandidateIdentityV1.model_fields

    source_ref = MemorySourceRefV1(source_type="conversation_message", run_id="run-1")
    identity = MemoryIdentityV1(
        tenant_id="tenant-1",
        memory_type="long_term_fact",
        scope_type="merchant",
        scope_id="merchant-1",
        content_hash=content_hash,
        source_identity_hash=source_identity_hash,
    )
    candidate_identity = MemoryCandidateIdentityV1(
        tenant_id="tenant-1",
        memory_type="long_term_fact",
        scope_type="merchant",
        scope_id="merchant-1",
        content_hash=content_hash,
        source_identity_hash=source_identity_hash,
        candidate_hash=candidate_hash,
    )

    assert source_ref.model_dump(exclude_none=True) == {
        "source_type": "conversation_message",
        "run_id": "run-1",
    }
    assert identity.content_hash == content_hash
    assert candidate_identity.candidate_hash == candidate_hash

    with pytest.raises(ValidationError):
        MemorySourceRefV1.model_validate({"source_type": "conversation_message", "raw_payload": {}})

    with pytest.raises(ValidationError):
        MemoryCandidateIdentityV1.model_validate(
            {
                "tenant_id": "tenant-1",
                "memory_type": "long_term_fact",
                "scope_type": "merchant",
                "scope_id": "merchant-1",
                "content_hash": content_hash,
                "source_identity_hash": source_identity_hash,
                "candidate_hash": candidate_hash,
                "approval_authority_body": {},
            }
        )


def test_v2_profile_preserves_proper_nouns_and_never_reinterprets_legacy_hashes() -> None:
    content = "  Acme Å  REFUND  "

    legacy_normalized = normalize_memory_content(
        content,
        identity_profile=LEGACY_MEMORY_IDENTITY_PROFILE,
    )
    current_normalized = normalize_memory_content(
        content,
        identity_profile=MEMORY_IDENTITY_PROFILE,
    )
    legacy_hash = canonical_memory_content_hash(
        memory_type="long_term_fact",
        content=content,
        identity_profile=LEGACY_MEMORY_IDENTITY_PROFILE,
    )
    current_hash = canonical_memory_content_hash(
        memory_type="long_term_fact",
        content=content,
        identity_profile=MEMORY_IDENTITY_PROFILE,
    )

    assert legacy_normalized == "acme å refund"
    assert current_normalized == "Acme Å REFUND"
    assert legacy_hash == "sha256:8a6b9657a7b3410a464d3c4a0222f74256a72f1133a889bdce925fd11dda08c5"
    assert current_hash == "sha256:e59d1ac3ce39b9db69f8036129be4af75d2694762be9a1796eb36728e54878e1"
    assert legacy_hash != current_hash


def test_all_memory_builders_use_the_shared_owner() -> None:
    tenant_id = UUID("10000000-0000-0000-0000-000000000001")
    user_id = UUID("20000000-0000-0000-0000-000000000002")
    run_id = UUID("30000000-0000-0000-0000-000000000003")
    case_id = UUID("40000000-0000-0000-0000-000000000004")
    timestamp = datetime(2026, 8, 5, 10, 0, tzinfo=UTC)
    source_ref = MemorySourceRefV1(
        source_type="explicit_user_preference",
        run_id=str(run_id),
        agent_run_id=str(run_id),
    )

    session_candidate = SessionMemoryWriteCandidate(
        tenant_id=tenant_id,
        user_id=user_id,
        thread_id="Thread-Acme",
        run_id=run_id,
        explicit_slots={
            "order_id": SessionSlotV1(
                value="ORD-Acme-1",
                source="explicit_user",
                source_run_id=str(run_id),
                updated_at=timestamp,
                expires_at=timestamp,
                confidence=0.9,
                compatible_intents=["refund_troubleshooting"],
            )
        },
        last_intent="refund_troubleshooting",
        session_summary="Acme requested a refund update.",
        last_business_context_refs={"order_id": "ORD-Acme-1"},
    )
    long_term_candidate = LongTermMemoryWriteCandidate(
        tenant_id=tenant_id,
        run_id=run_id,
        scope_type="merchant",
        scope_id="Merchant-Acme",
        content="Acme prefers concise refund updates.",
        source_type="explicit_user_preference",
        source_ref=source_ref,
    )
    case_candidate = CaseMemoryWriteCandidate(
        tenant_id=tenant_id,
        run_id=run_id,
        scope_type="case",
        scope_id=str(case_id),
        case_type="refund_dispute",
        summary="Acme refund precedent",
        excerpt="Acme received a manual review.",
        source_type="human_reviewed",
        source_ref=source_ref.model_copy(update={"source_type": "human_reviewed"}),
    )
    cwc_candidate = CaseWorkingContextWriteCandidate(
        tenant_id=tenant_id,
        case_id=case_id,
        updated_by_run_id=run_id,
        source_ref=source_ref.model_copy(
            update={
                "source_type": "case_working_context_write",
                "business_object_type": "refund_case",
                "business_object_id": str(case_id),
            }
        ),
        content=CaseWorkingContextContentV1(
            customer_request="Acme requests a refund update.",
            issue_type="refund_dispute",
        ),
    )

    identities = (
        build_session_memory_candidate_identity(session_candidate),
        build_long_term_memory_candidate_identity(long_term_candidate),
        build_case_memory_candidate_identity(case_candidate),
        build_case_working_context_candidate_identity(cwc_candidate),
    )

    assert all(isinstance(identity, MemoryCandidateIdentityV1) for identity in identities)
    assert all(identity.identity_profile == MEMORY_IDENTITY_PROFILE for identity in identities)
    assert all(SHA256_RE.fullmatch(identity.content_hash) for identity in identities)
    assert all(SHA256_RE.fullmatch(identity.source_identity_hash or "") for identity in identities)
    assert all(SHA256_RE.fullmatch(identity.candidate_hash) for identity in identities)
    assert identities[0] == build_session_memory_candidate_identity(session_candidate)
    assert identities[0].normalized_source_ref.agent_run_id == str(run_id)

    changed_session = session_candidate.model_copy(update={"reason_code": "temporary_chat"})
    assert identities[0].content_hash != build_session_memory_candidate_identity(changed_session).content_hash
    assert identities[0].candidate_hash != build_session_memory_candidate_identity(changed_session).candidate_hash


def test_typed_builders_reject_unknown_fields_and_incomplete_sources() -> None:
    with pytest.raises(MemoryIdentityError, match="unknown|extra"):
        build_long_term_memory_candidate_identity(
            {
                "tenant_id": "10000000-0000-0000-0000-000000000001",
                "run_id": "30000000-0000-0000-0000-000000000003",
                "scope_type": "merchant",
                "scope_id": "merchant-1",
                "content": "Acme preference",
                "source_type": "explicit_user_preference",
                "unexpected": "must fail closed",
            }
        )

    with pytest.raises(MemoryIdentityError, match="run_id|required|discriminator"):
        build_long_term_memory_candidate_identity(
            {
                "tenant_id": "10000000-0000-0000-0000-000000000001",
                "scope_type": "merchant",
                "scope_id": "merchant-1",
                "content": "Acme preference",
                "source_type": "explicit_user_preference",
            }
        )

    with pytest.raises(MemoryIdentityError, match="identity profile"):
        normalize_memory_content("Acme", identity_profile="unknown")


class _NestedTransaction:
    async def __aenter__(self):
        return None

    async def __aexit__(self, exc_type, exc, traceback):
        return False


class _SessionIdentityRepository:
    def __init__(self, *, conflict: bool = False) -> None:
        self.session = SimpleNamespace(begin_nested=lambda: _NestedTransaction())
        self.conflict = conflict
        self.events: list[SimpleNamespace] = []
        self.active = (
            SimpleNamespace(
                id=uuid4(),
                version=1,
                expires_at=None,
                active_slots_json={"schema_version": "session_slots.v1", "slots": {}},
                last_business_context_refs_json={},
                session_summary=None,
                unresolved_questions_json=[],
                last_intent="order_status_inquiry",
            )
            if conflict
            else None
        )

    async def get_active(self, *args, **kwargs):
        return self.active

    async def insert_active(self, **kwargs):
        self.active = SimpleNamespace(id=uuid4(), version=1)
        return self.active

    async def cas_update(self, *args, **kwargs):
        return False if self.conflict else True

    async def emit_write_event(self, **kwargs):
        event = SimpleNamespace(id=uuid4(), **kwargs)
        self.events.append(event)
        return event


def _session_identity_candidate(*, decision: str = "write") -> SessionMemoryWriteCandidate:
    return SessionMemoryWriteCandidate(
        tenant_id=UUID("10000000-0000-0000-0000-000000000001"),
        user_id=UUID("20000000-0000-0000-0000-000000000002"),
        thread_id="Thread-Acme",
        run_id=UUID("30000000-0000-0000-0000-000000000003"),
        last_intent="refund_troubleshooting",
        session_summary="Acme requested an update.",
        decision=decision,
        reason_code="temporary_chat" if decision == "skip" else "eligible",
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["written", "skipped", "conflict"])
async def test_session_service_reuses_one_typed_identity_for_result_and_event(
    monkeypatch,
    path: str,
) -> None:
    from src.memory import service as service_module

    repository = _SessionIdentityRepository(conflict=path == "conflict")
    candidate = _session_identity_candidate(decision="skip" if path == "skipped" else "write")
    calls: list[SessionMemoryWriteCandidate] = []
    real_builder = service_module.build_session_memory_candidate_identity

    def spy_builder(value):
        calls.append(value)
        return real_builder(value)

    monkeypatch.setattr(service_module, "build_session_memory_candidate_identity", spy_builder)

    result = await MemoryService(repository).write_session_memory(candidate)  # type: ignore[arg-type]

    assert len(calls) == 1
    assert result.identity == real_builder(candidate)
    assert result.candidate_hash == result.identity.candidate_hash
    assert result.identity.content_hash.startswith("sha256:")
    assert result.identity.source_identity_hash is not None
    assert repository.events[0].candidate_hash == result.identity.candidate_hash
    assert repository.events[0].source_ref_json == result.identity.normalized_source_ref.model_dump(
        mode="json", exclude_none=True
    )


class _CandidateWriteRepository:
    def __init__(self) -> None:
        self.identity_kwargs: dict[str, Any] = {}
        self.event_kwargs: dict[str, Any] = {}

    async def check_tombstone_before_write(self, **kwargs):
        return None

    async def get_exact_identity_claim(self, **kwargs):
        return None

    async def retire_expired_current_by_content_hash(self, **kwargs):
        return None

    async def retire_unpublished_current_by_content_hash(self, **kwargs):
        return None

    async def get_active_by_content_hash(self, **kwargs):
        return None

    async def get_active_duplicate(self, **kwargs):
        return None

    async def insert_memory(self, candidate, **kwargs):
        self.identity_kwargs = kwargs
        return SimpleNamespace(id=uuid4(), review_status=kwargs["review_status"])

    async def insert_case_memory(self, candidate, **kwargs):
        self.identity_kwargs = kwargs
        return SimpleNamespace(id=uuid4(), review_status=kwargs["review_status"])

    async def create_identity_claim(self, *, memory):
        return SimpleNamespace(owner_case_memory_id=memory.id)

    async def emit_write_event(self, **kwargs):
        self.event_kwargs = kwargs
        return SimpleNamespace(id=uuid4())


@pytest.mark.asyncio
async def test_long_term_and_case_services_call_named_owner_once_and_persist_exact_result(monkeypatch) -> None:
    from src.memory import case_memory as case_module
    from src.memory import long_term as long_term_module

    tenant_id = UUID("10000000-0000-0000-0000-000000000001")
    run_id = UUID("30000000-0000-0000-0000-000000000003")
    long_term_candidate = LongTermMemoryWriteCandidate(
        tenant_id=tenant_id,
        run_id=run_id,
        scope_type="merchant",
        scope_id="Merchant-Acme",
        content="Acme prefers concise updates.",
        source_type="explicit_user_preference",
    )
    case_candidate = CaseMemoryWriteCandidate(
        tenant_id=tenant_id,
        run_id=run_id,
        scope_type="case",
        scope_id="Case-Acme",
        case_type="refund_dispute",
        summary="Acme reviewed precedent.",
        excerpt="Acme received a reviewed refund.",
        source_type="human_reviewed",
    )
    long_calls: list[LongTermMemoryWriteCandidate] = []
    case_calls: list[CaseMemoryWriteCandidate] = []
    real_long_builder = build_long_term_memory_candidate_identity
    real_case_builder = build_case_memory_candidate_identity

    def spy_long(value):
        long_calls.append(value)
        return real_long_builder(value)

    def spy_case(value):
        case_calls.append(value)
        return real_case_builder(value)

    monkeypatch.setattr(long_term_module, "build_long_term_memory_candidate_identity", spy_long)
    monkeypatch.setattr(case_module, "build_case_memory_candidate_identity", spy_case)
    long_repository = _CandidateWriteRepository()
    case_repository = _CandidateWriteRepository()

    long_result = await long_term_module.LongTermMemoryService(long_repository).write_memory(long_term_candidate)
    case_result = await case_module.CaseMemoryService(case_repository).submit_case_memory_candidate(case_candidate)

    for calls, candidate, result, repository, builder in (
        (long_calls, long_term_candidate, long_result, long_repository, real_long_builder),
        (case_calls, case_candidate, case_result, case_repository, real_case_builder),
    ):
        expected = builder(candidate)
        assert calls == [candidate]
        assert result.candidate_hash == expected.candidate_hash
        assert result.content_hash == expected.content_hash
        assert result.source_identity_hash == expected.source_identity_hash
        assert repository.identity_kwargs["content_hash"] == expected.content_hash
        assert repository.identity_kwargs["source_identity_hash"] == expected.source_identity_hash
        assert repository.event_kwargs["candidate_hash"] == expected.candidate_hash
        assert repository.event_kwargs["source_ref_json"] == expected.normalized_source_ref.model_dump(
            mode="json", exclude_none=True
        )


@pytest.mark.asyncio
async def test_cwc_service_calls_named_owner_once_and_events_exact_result(monkeypatch) -> None:
    from src.memory import case_working_context_service as cwc_module

    tenant_id = UUID("10000000-0000-0000-0000-000000000001")
    run_id = UUID("30000000-0000-0000-0000-000000000003")
    case_id = UUID("40000000-0000-0000-0000-000000000004")
    candidate = CaseWorkingContextWriteCandidate(
        tenant_id=tenant_id,
        case_id=case_id,
        source_ref=MemorySourceRefV1(
            source_type="case_working_context_write",
            run_id=str(run_id),
            agent_run_id=str(run_id),
            business_object_type="refund_case",
            business_object_id=str(case_id),
        ),
        content=CaseWorkingContextContentV1(customer_request="Acme requests an update."),
    )
    calls: list[CaseWorkingContextWriteCandidate] = []
    event_kwargs: dict[str, Any] = {}
    real_builder = build_case_working_context_candidate_identity

    def spy_builder(value):
        calls.append(value)
        return real_builder(value)

    async def run_isolated(parent_session, operation):
        return await operation(SimpleNamespace())

    async def allow_scope(*args, **kwargs):
        return None

    class FakeCwcRepository:
        def __init__(self, session) -> None:
            pass

        async def write_working_context(self, trusted_candidate):
            return SimpleNamespace(status="written", case_working_context_id=uuid4(), version=1)

    async def emit_event(session, **kwargs):
        event_kwargs.update(kwargs)
        return SimpleNamespace(id=uuid4())

    monkeypatch.setattr(cwc_module, "build_case_working_context_candidate_identity", spy_builder)
    monkeypatch.setattr(cwc_module, "run_memory_side_effect_in_isolated_session", run_isolated)
    monkeypatch.setattr(cwc_module, "_assert_run_belongs_to_tenant", allow_scope)
    monkeypatch.setattr(cwc_module, "_assert_case_belongs_to_tenant", allow_scope)
    monkeypatch.setattr(cwc_module, "CaseWorkingContextRepository", FakeCwcRepository)
    monkeypatch.setattr(cwc_module, "_emit_write_event", emit_event)

    result = await cwc_module.CaseWorkingContextService().write_case_working_context(
        SimpleNamespace(),
        candidate,
        run_id=run_id,
    )
    trusted_candidate = cwc_module._trusted_write_candidate(candidate=candidate, run_id=run_id)
    expected = real_builder(trusted_candidate)

    assert calls == [trusted_candidate]
    assert result.candidate_hash == expected.candidate_hash
    assert event_kwargs["candidate_hash"] == expected.candidate_hash
    assert event_kwargs["source_ref_json"] == expected.normalized_source_ref.model_dump(
        mode="json", exclude_none=True
    )


def test_memory_callers_have_no_local_candidate_identity_builders() -> None:
    from src.memory import case_memory, case_working_context_service, long_term

    sources = {
        "long_term": inspect.getsource(long_term),
        "case_memory": inspect.getsource(case_memory),
        "case_working_context": inspect.getsource(case_working_context_service),
    }

    assert "def _candidate_identity" not in sources["long_term"]
    assert "def _candidate_hash_for_memory" not in sources["long_term"]
    assert "def _candidate_identity" not in sources["case_memory"]
    assert "def _candidate_hash_for_memory" not in sources["case_memory"]
    assert "def _candidate_hash(" not in sources["case_working_context"]
