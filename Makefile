.PHONY: up down migrate seed test lint format dev eval eval-rag eval-agent eval-live eval-baseline

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

eval-agent:
	uv run python scripts/eval_agent.py

eval-live:
	uv run python scripts/eval_all.py --agent-mode live

eval-baseline:
	uv run python scripts/eval_all.py --save-baseline
