"""Durable, opaque one-use authority for the sole demo draft handler."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import hashlib
import json
import re
import secrets
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.approvals.schemas import RiskDecisionV1
from src.db.models import ActionSafetySnapshot, AgentRun, AutoActionCapability
from src.platform.trusted_context import MerchantScopeV1
from src.repositories.action_draft_repo import ActionDraftRepository


AUTO_ACTION_CAPABILITY_SCHEMA_VERSION = "auto_action_capability.v1"
AUTO_ACTION_CAPABILITY_REF_SCHEMA_VERSION = "auto_action_capability_ref.v1"
AUTO_ACTION_CAPABILITY_KEY_VERSION = "opaque_ref_sha256.v1"
AUTO_ACTION_CAPABILITY_HANDLER = "create_coupon_grant_draft"
AUTO_ACTION_CAPABILITY_TTL = timedelta(minutes=5)
_AUTO_ACTION_CAPABILITY_REF_PATTERN = re.compile(r"^aac_[A-Za-z0-9_-]+$")


class CapabilityMintError(ValueError):
    """Trusted mint prerequisites were not satisfied."""


class CapabilityVerificationError(ValueError):
    """A capability is absent, expired, consumed incorrectly, or mis-bound."""

    def __init__(self, error_code: str, message: str) -> None:
        super().__init__(message)
        self.error_code = error_code


class AutoActionCapabilityRefV1(BaseModel):
    """Bearer projection carried by graph state; binding truth remains server-side."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["auto_action_capability_ref.v1"] = AUTO_ACTION_CAPABILITY_REF_SCHEMA_VERSION
    capability_ref: str = Field(min_length=32, pattern=r"^aac_[A-Za-z0-9_-]+$")
    expires_at: datetime


class VerifiedAutoActionCapability(BaseModel):
    """Internal locked capability selection result."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    capability: AutoActionCapability
    already_consumed: bool


def capability_ref_digest(capability_ref: str) -> str:
    raw_ref = str(capability_ref or "")
    return f"sha256:{hashlib.sha256(raw_ref.encode('utf-8')).hexdigest()}"


def is_opaque_capability_ref(value: Any) -> bool:
    """Return whether a raw value is shaped for authoritative service verification."""

    return (
        isinstance(value, str)
        and len(value) >= 32
        and _AUTO_ACTION_CAPABILITY_REF_PATTERN.fullmatch(value) is not None
    )


def compute_merchant_scope_hash(
    merchant_scope: MerchantScopeV1 | dict[str, Any] | list[str],
) -> str:
    scope = _merchant_scope(merchant_scope)
    encoded = json.dumps(
        scope.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def compute_risk_decision_hash(risk_decision: dict[str, Any] | RiskDecisionV1) -> str:
    canonical = (
        risk_decision
        if isinstance(risk_decision, RiskDecisionV1)
        else RiskDecisionV1.model_validate(risk_decision)
    ).model_dump(mode="json")
    encoded = json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


class AutoActionCapabilityService:
    """Only owner allowed to mint, lock, verify, and transition auto capability rows."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        repository: ActionDraftRepository | None = None,
    ) -> None:
        self.session = session
        self.repository = repository or ActionDraftRepository(session)

    async def mint(
        self,
        *,
        tenant_id: UUID,
        actor_id: UUID,
        run_id: UUID,
        merchant_scope: MerchantScopeV1 | dict[str, Any] | list[str],
        target_merchant_id: str,
        canonical_action: str,
        action_payload_hash: str,
        safety_snapshot_ref: str,
        safety_snapshot_hash: str,
        risk_decision_ref: str,
        risk_decision: dict[str, Any] | RiskDecisionV1,
        risk_disposition: str,
        handler: str = AUTO_ACTION_CAPABILITY_HANDLER,
        ttl: timedelta = AUTO_ACTION_CAPABILITY_TTL,
    ) -> AutoActionCapabilityRefV1:
        tenant_uuid = _as_uuid_for_mint(tenant_id)
        actor_uuid = _as_uuid_for_mint(actor_id)
        run_uuid = _as_uuid_for_mint(run_id)
        merchant_id = str(target_merchant_id or "").strip()
        action = str(canonical_action or "").strip()
        risk_ref = str(risk_decision_ref or "").strip()
        if (
            not merchant_id
            or action != "issue_coupon"
            or handler != AUTO_ACTION_CAPABILITY_HANDLER
            or risk_disposition != "allow"
            or ttl <= timedelta(0)
            or ttl > AUTO_ACTION_CAPABILITY_TTL
        ):
            raise CapabilityMintError("Auto-action capability mint prerequisites are invalid")

        try:
            trusted_scope = _merchant_scope(merchant_scope)
        except ValueError as exc:
            raise CapabilityMintError("Trusted merchant scope is invalid") from exc
        if not trusted_scope.allows(merchant_id=merchant_id):
            raise CapabilityMintError("Target merchant is outside trusted merchant scope")

        try:
            trusted_risk = (
                risk_decision
                if isinstance(risk_decision, RiskDecisionV1)
                else RiskDecisionV1.model_validate(risk_decision)
            )
        except ValueError as exc:
            raise CapabilityMintError("Risk decision is invalid") from exc
        if (
            trusted_risk.tenant_id != str(tenant_uuid)
            or trusted_risk.run_id != str(run_uuid)
            or trusted_risk.action_payload_hash != action_payload_hash
            or trusted_risk.risk_level != "low"
            or trusted_risk.approval_required is not False
            or not trusted_risk.risk_rule_ref
            or "risk_disposition:allow" not in trusted_risk.reason_codes
            or not risk_ref
        ):
            raise CapabilityMintError("Risk decision does not prove deterministic allow")

        run = (
            await self.session.execute(
                select(AgentRun).where(
                    AgentRun.id == run_uuid,
                    AgentRun.tenant_id == tenant_uuid,
                    AgentRun.user_id == actor_uuid,
                )
            )
        ).scalar_one_or_none()
        if run is None:
            raise CapabilityMintError("Trusted run actor binding is invalid")

        snapshot = (
            await self.session.execute(
                select(ActionSafetySnapshot).where(
                    ActionSafetySnapshot.tenant_id == tenant_uuid,
                    ActionSafetySnapshot.run_id == run_uuid,
                    ActionSafetySnapshot.snapshot_ref == safety_snapshot_ref,
                    ActionSafetySnapshot.immutable_hash == safety_snapshot_hash,
                    ActionSafetySnapshot.action_payload_hash == action_payload_hash,
                    ActionSafetySnapshot.target_merchant_id == merchant_id,
                    ActionSafetySnapshot.deleted_at.is_(None),
                )
            )
        ).scalar_one_or_none()
        if snapshot is None:
            raise CapabilityMintError("Persisted action safety snapshot binding is invalid")

        issued_at = _utcnow()
        expires_at = issued_at + ttl
        raw_ref = f"aac_{secrets.token_urlsafe(32)}"
        await self.repository.create_capability(
            schema_version=AUTO_ACTION_CAPABILITY_SCHEMA_VERSION,
            key_version=AUTO_ACTION_CAPABILITY_KEY_VERSION,
            opaque_ref=capability_ref_digest(raw_ref),
            nonce=uuid4().hex,
            tenant_id=tenant_uuid,
            actor_id=actor_uuid,
            run_id=run_uuid,
            merchant_scope_hash=compute_merchant_scope_hash(trusted_scope),
            target_merchant_id=merchant_id,
            canonical_action=action,
            action_payload_hash=action_payload_hash,
            safety_snapshot_ref=safety_snapshot_ref,
            safety_snapshot_hash=safety_snapshot_hash,
            risk_decision_ref=risk_ref,
            risk_decision_hash=compute_risk_decision_hash(trusted_risk),
            risk_disposition="allow",
            handler=AUTO_ACTION_CAPABILITY_HANDLER,
            issued_at=issued_at,
            expires_at=expires_at,
            status="issued",
        )
        return AutoActionCapabilityRefV1(capability_ref=raw_ref, expires_at=expires_at)

    async def lock_and_verify_for_draft(
        self,
        *,
        capability_ref: str,
        tenant_id: UUID,
        actor_id: UUID,
        run_id: UUID,
        merchant_scope: MerchantScopeV1 | dict[str, Any] | list[str],
        target_merchant_id: str,
        canonical_action: str,
        action_payload_hash: str,
        safety_snapshot_ref: str,
        safety_snapshot_hash: str,
        risk_decision_ref: str,
        risk_decision: dict[str, Any] | RiskDecisionV1,
        handler: str,
    ) -> VerifiedAutoActionCapability:
        capability = await self.repository.lock_capability_by_opaque_ref(
            capability_ref_digest(capability_ref)
        )
        if capability is None:
            raise CapabilityVerificationError(
                "AUTO_ACTION_CAPABILITY_MISMATCH",
                "Auto-action capability binding is invalid",
            )

        if capability.status == "issued" and capability.expires_at <= _utcnow():
            await self.repository.mark_capability_expired(capability)
            raise CapabilityVerificationError(
                "AUTO_ACTION_CAPABILITY_EXPIRED",
                "Auto-action capability has expired",
            )
        if capability.status == "expired":
            raise CapabilityVerificationError(
                "AUTO_ACTION_CAPABILITY_EXPIRED",
                "Auto-action capability has expired",
            )
        if capability.status == "revoked":
            raise CapabilityVerificationError(
                "AUTO_ACTION_CAPABILITY_REVOKED",
                "Auto-action capability is revoked",
            )
        if capability.status not in {"issued", "consumed"}:
            raise CapabilityVerificationError(
                "AUTO_ACTION_CAPABILITY_MISMATCH",
                "Auto-action capability binding is invalid",
            )

        try:
            risk_hash = compute_risk_decision_hash(risk_decision)
            expected_tenant_id = _as_uuid_for_verify(tenant_id)
            expected_actor_id = _as_uuid_for_verify(actor_id)
            expected_run_id = _as_uuid_for_verify(run_id)
            trusted_scope = _merchant_scope(merchant_scope)
            merchant_scope_hash = compute_merchant_scope_hash(trusted_scope)
        except (ValueError, CapabilityVerificationError) as exc:
            raise CapabilityVerificationError(
                "AUTO_ACTION_CAPABILITY_MISMATCH",
                "Auto-action capability binding is invalid",
            ) from exc
        if not trusted_scope.allows(merchant_id=str(target_merchant_id or "")):
            raise CapabilityVerificationError(
                "AUTO_ACTION_CAPABILITY_MISMATCH",
                "Auto-action capability binding is invalid",
            )
        expected = (
            expected_tenant_id,
            expected_actor_id,
            expected_run_id,
            merchant_scope_hash,
            str(target_merchant_id or ""),
            str(canonical_action or ""),
            str(action_payload_hash or ""),
            str(safety_snapshot_ref or ""),
            str(safety_snapshot_hash or ""),
            str(risk_decision_ref or ""),
            risk_hash,
            handler,
        )
        actual = (
            capability.tenant_id,
            capability.actor_id,
            capability.run_id,
            capability.merchant_scope_hash,
            capability.target_merchant_id,
            capability.canonical_action,
            capability.action_payload_hash,
            capability.safety_snapshot_ref,
            capability.safety_snapshot_hash,
            capability.risk_decision_ref,
            capability.risk_decision_hash,
            capability.handler,
        )
        if (
            actual != expected
            or capability.schema_version != AUTO_ACTION_CAPABILITY_SCHEMA_VERSION
            or capability.key_version != AUTO_ACTION_CAPABILITY_KEY_VERSION
            or capability.risk_disposition != "allow"
        ):
            raise CapabilityVerificationError(
                "AUTO_ACTION_CAPABILITY_MISMATCH",
                "Auto-action capability binding is invalid",
            )
        return VerifiedAutoActionCapability(
            capability=capability,
            already_consumed=capability.status == "consumed",
        )

    async def mark_consumed(
        self,
        capability: AutoActionCapability,
        *,
        draft_id: UUID,
        idempotency_key: str,
    ) -> None:
        if capability.status != "issued":
            raise CapabilityVerificationError(
                "AUTO_ACTION_CAPABILITY_REPLAY",
                "Auto-action capability was already consumed",
            )
        await self.repository.mark_capability_consumed(
            capability,
            draft_id=draft_id,
            idempotency_key=idempotency_key,
            consumed_at=_utcnow(),
        )


def _as_uuid_for_mint(value: UUID | str) -> UUID:
    if isinstance(value, UUID):
        return value
    try:
        return UUID(str(value))
    except (TypeError, ValueError) as exc:
        raise CapabilityMintError("Capability identity is invalid") from exc


def _merchant_scope(
    value: MerchantScopeV1 | dict[str, Any] | list[str],
) -> MerchantScopeV1:
    if isinstance(value, MerchantScopeV1):
        return value
    if isinstance(value, list):
        return MerchantScopeV1(merchant_ids=value)
    return MerchantScopeV1.model_validate(value)


def _as_uuid_for_verify(value: UUID | str) -> UUID:
    if isinstance(value, UUID):
        return value
    try:
        return UUID(str(value))
    except (TypeError, ValueError) as exc:
        raise CapabilityVerificationError(
            "AUTO_ACTION_CAPABILITY_MISMATCH",
            "Auto-action capability binding is invalid",
        ) from exc


def _utcnow() -> datetime:
    return datetime.now(UTC)
