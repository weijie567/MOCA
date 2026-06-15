# Phase 13 Approval State Machine Migration Report

## alembic_current_before

alembic_current_before: 005_approval_tables

## alembic_head_before

alembic_head_before: 008_approval_state_machine

## legacy_v1_count

legacy_v1_count: 0

## legacy_non_executable_count

legacy_non_executable_count: 0

No local legacy rows required quarantine during this execution. Migration 008 still
backfills legacy rows with deterministic `row_number()` revisions per `(tenant_id,
run_id)` and sets `legacy_non_executable=true` before creating
`uq_approval_requests_tenant_run_revision`.

## read_switch_owner

read_switch_owner: src/approvals/repository.py

## fallback_behavior

fallback_behavior: legacy_v1_rows_display_reject_cancel_expire_supersede_only

## rollback_command

rollback_command: uv run alembic downgrade 007_session_memories

Rollback is explicit and local-only for this schema expansion. Downgrade drops Phase
13 target tables and v2 approval request columns/indexes/constraints; no external
side effects are introduced.

## verification_commands

- `uv run alembic upgrade head`
- `uv run pytest tests/approvals/test_migration_contract.py tests/approvals/test_multi_level_contract.py -q --tb=short`

## observed_after_upgrade

alembic_current_after: 008_approval_state_machine
alembic_head_after: 008_approval_state_machine
