# Phase 13 Approval State Machine Migration Report

## alembic_current_before

pending_task_4

## alembic_head_before

pending_task_4

## legacy_v1_count

pending_task_4

## legacy_non_executable_count

pending_task_4

## read_switch_owner

pending_task_4

## fallback_behavior

pending_task_4

## rollback_command

pending_task_4

Target rollback command: `uv run alembic downgrade 007_session_memories`

## verification_commands

- `uv run alembic upgrade head`
- `uv run pytest tests/approvals/test_migration_contract.py tests/approvals/test_multi_level_contract.py -q --tb=short`
