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
	uv run fastapi dev src/api/main.py
