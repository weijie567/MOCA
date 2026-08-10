.PHONY: up down migrate seed test lint format dev eval eval-rag eval-agent eval-live eval-baseline eval-rag-format-parity-contract eval-rag-format-parity-parser eval-rag-format-parity-provider

up:
	docker compose up --build

down:
	docker compose down

migrate:
	uv run alembic upgrade head

seed:
	uv run python scripts/seed_demo.py --reset

test:
	uv run pytest

lint:
	uv run ruff check src/ tests/

format:
	uv run ruff format src/ tests/

dev:
	uv run uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload

eval:
	uv run python scripts/eval_all.py

eval-rag:
	uv run python scripts/eval_rag.py

eval-rag-format-parity-contract:
	UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/eval/test_rag_format_parity_contract.py tests/eval/test_rag_parser_parity.py tests/eval/test_rag_retrieval_round_isolation.py tests/eval/test_rag_format_parity_report.py -q --tb=short

eval-rag-format-parity-parser:
	UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/eval_rag_parser_parity.py --manifest evaluation/rag_sources/format_parity_manifest.jsonl --gold evaluation/golden/rag_format_parity_gold.json --output evaluation/reports/rag_parser_parity.json

eval-rag-format-parity-provider:
	@test -n "$$RAG_FORMAT_PARITY_RUN_TOKEN" || (echo "RAG_FORMAT_PARITY_RUN_TOKEN is required" >&2; exit 2)
	@test -n "$$EVIDENCE_ROLLOUT_VERSION" || (echo "EVIDENCE_ROLLOUT_VERSION is required" >&2; exit 2)
	UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/eval_rag_format_parity.py --mode full-provider --manifest evaluation/rag_sources/format_parity_manifest.jsonl --gold evaluation/golden/rag_format_parity_gold.json --tenant-id 64300000-0000-4000-8000-000000000001 --owner-marker moca.rag_format_parity.v1 --run-token "$$RAG_FORMAT_PARITY_RUN_TOKEN" --expected-rollout-version "$$EVIDENCE_ROLLOUT_VERSION" --output-dir evaluation/reports/rag_format_parity/v1 --diagnostic-output "evaluation/reports/rag_format_parity/v1/diagnostics/$$RAG_FORMAT_PARITY_RUN_TOKEN.json"

eval-agent:
	uv run python scripts/eval_agent.py

eval-live:
	uv run python scripts/eval_all.py --agent-mode live

eval-baseline:
	uv run python scripts/eval_all.py --save-baseline
