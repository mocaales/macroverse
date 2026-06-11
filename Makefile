BACKEND_PYTHON := backend/.venv/bin/python
BACKEND_UVICORN := backend/.venv/bin/uvicorn
BACKEND_PYTEST := backend/.venv/bin/pytest
BACKEND_RUFF := backend/.venv/bin/ruff

.PHONY: install backend frontend migrate sync-fred sync-bitcoin sync-all test lint build docker-up docker-down

install:
	python3 -m venv backend/.venv
	$(BACKEND_PYTHON) -m pip install -e "backend[dev]"
	cd frontend && npm ci

backend:
	cd backend && .venv/bin/uvicorn app.main:app --reload

frontend:
	cd frontend && npm run dev

migrate:
	cd backend && .venv/bin/python -m app.cli migrate

sync-fred:
	cd backend && .venv/bin/python -m app.cli sync-fred

sync-bitcoin:
	cd backend && .venv/bin/python -m app.cli sync-bitcoin

sync-all:
	cd backend && .venv/bin/python -m app.cli sync-all

test:
	cd backend && .venv/bin/pytest
	cd frontend && npm run build

lint:
	cd backend && .venv/bin/ruff check .
	cd frontend && npm run lint

build:
	cd frontend && npm run build

docker-up:
	docker compose up --build

docker-down:
	docker compose down
