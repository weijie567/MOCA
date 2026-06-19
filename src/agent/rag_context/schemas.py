"""Strict DTOs for Phase 22 RAG context bundles."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from src.knowledge.schemas import EvidenceRefV1
from src.tools.contracts import BusinessFactRefV1


class RagContextBudget(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max_prompt_chars: int = Field(default=8_000, ge=1)
    max_snippet_chars: int = Field(default=220, ge=1)
    max_evidence_items: int = Field(default=5, ge=1)


class EvidenceTraceEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence_id: str
    reason_code: str
    reason_codes: list[str] = Field(default_factory=list)
    citation_id: str | None = None
    doc_key: str | None = None
    chunk_id: str | None = None


class PromptCitation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    citation_id: str
    display_label: str
    snippet: str
    risk_labels: list[str] = Field(default_factory=list)
    metadata: dict[str, str] = Field(default_factory=dict)
    merged_from_chunk_ids: list[str] = Field(default_factory=list)


class CitationMapEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    citation_id: str
    evidence_ref: EvidenceRefV1
    source_evidence_ids: list[str]
    snippet: str
    risk_labels: list[str] = Field(default_factory=list)
    metadata: dict[str, str] = Field(default_factory=dict)
    merged_from_chunk_ids: list[str] = Field(default_factory=list)


class RagPromptContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rag_prompt_context.v1"] = "rag_prompt_context.v1"
    citations: list[PromptCitation] = Field(default_factory=list)
    risk_labels: list[str] = Field(default_factory=list)
    trusted_context: dict[str, str] = Field(default_factory=dict)


class RagVerifierContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rag_verifier_context.v1"] = "rag_verifier_context.v1"
    evidence_snippets: list[dict[str, Any]] = Field(default_factory=list)
    business_fact_refs: list[BusinessFactRefV1] = Field(default_factory=list)
    safe_refs: list[str] = Field(default_factory=list)


class RagDebugContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rag_debug_context.v1"] = "rag_debug_context.v1"
    included_evidence: list[EvidenceTraceEntry] = Field(default_factory=list)
    truncated_or_excluded_evidence: list[EvidenceTraceEntry] = Field(default_factory=list)
    raw_risk_hints: list[dict[str, Any]] = Field(default_factory=list)


class RagSafeContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rag_safe_context.v1"] = "rag_safe_context.v1"
    citations: list[PromptCitation] = Field(default_factory=list)
    risk_labels: list[str] = Field(default_factory=list)


class RagContextBudgetTrace(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max_prompt_chars: int
    protected_metadata_preserved: bool = True
    included: list[EvidenceTraceEntry] = Field(default_factory=list)
    truncated: list[EvidenceTraceEntry] = Field(default_factory=list)
    excluded: list[EvidenceTraceEntry] = Field(default_factory=list)


class RagContextBuildInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_evidence_refs: list[EvidenceRefV1] = Field(default_factory=list)
    business_fact_refs: list[BusinessFactRefV1] = Field(default_factory=list)
    trusted_context: dict[str, Any]
    risk_hints: list[dict[str, Any]] = Field(default_factory=list)


class RagContextBundle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rag_context_bundle.v1"] = "rag_context_bundle.v1"
    tenant_id: str
    trusted_context: dict[str, Any]
    citation_map: dict[str, CitationMapEntry] = Field(default_factory=dict)
    prompt_context: RagPromptContext
    verifier_context: RagVerifierContext
    debug_context: RagDebugContext
    final_response_context: RagSafeContext
    memory_context: RagSafeContext
    replay_context: RagSafeContext
    business_fact_context: RagSafeContext
    action_snapshot_context: RagSafeContext
    budget_trace: RagContextBudgetTrace
