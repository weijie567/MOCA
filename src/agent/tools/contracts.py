from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


ToolRiskLevel = Literal["read", "retrieval", "write", "approval"]
ToolSideEffect = Literal["none", "read_only", "retrieval", "write", "approval_mutation"]
ToolCaller = Literal["investigator", "load_business_context", "retrieve_policy_evidence", "execute_action"]
ToolResultStatus = Literal["success", "error"]
ToolErrorCode = Literal["not_found", "unsafe_tool_request", "validation_error", "tool_error"]


class ToolInvocationContext(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")

    tenant_id: str
    user_id: str
    role: str
    session: Any
    caller: ToolCaller


class ToolRegistryEntry(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")

    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    input_schema: type[BaseModel]
    output_schema: type[BaseModel]
    risk_level: ToolRiskLevel
    side_effect: ToolSideEffect
    allowed_in_investigator: bool
    when_to_use: str = Field(min_length=1)
    required_identifiers: list[str]
    result_summary_fields: list[str]

    @model_validator(mode="after")
    def validate_investigator_safety(self) -> ToolRegistryEntry:
        if not self.allowed_in_investigator:
            return self
        if self.risk_level not in {"read", "retrieval"}:
            raise ValueError("investigator tools must use read or retrieval risk levels")
        if self.side_effect not in {"none", "read_only", "retrieval"}:
            raise ValueError("investigator tools must not declare write or approval side effects")
        return self


class ToolEvidenceRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    doc_key: str | None = None
    chunk_id: str | None = None
    title: str | None = None
    source: str | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)


class ToolExecutionError(BaseModel):
    model_config = ConfigDict(extra="forbid")

    error_code: ToolErrorCode
    message: str
    retryable: bool = False


class ToolExecutionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: ToolResultStatus
    error: ToolExecutionError | None = None
    evidence_refs: list[ToolEvidenceRef] = Field(default_factory=list)
    summary: dict[str, Any] = Field(default_factory=dict)
