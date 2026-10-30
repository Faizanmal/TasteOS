# TasteOS helpers (GNU Make). Without Make, use PowerShell/bash commands in README.
.PHONY: install api web lint typecheck test build docker-config docker-up docker-down check-qloo

ifeq ($(OS),Windows_NT)
ROOT_PY=..\..\.venv\Scripts\python.exe
INSTALL_PY=.venv\Scripts\python.exe
else
ROOT_PY=../../.venv/bin/python
INSTALL_PY=.venv/bin/python
endif

install:
	python -m venv .venv
	$(INSTALL_PY) -m pip install -U pip
	$(INSTALL_PY) -m pip install -e "apps/api[dev]"
	cd apps/web && npm install

api:
	cd apps/api && $(ROOT_PY) -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

web:
	cd apps/web && npm run dev

lint:
	cd apps/api && $(ROOT_PY) -m ruff check app tests
	cd apps/web && npm run lint

typecheck:
	cd apps/web && npm run typecheck

test:
	cd apps/api && $(ROOT_PY) -m pytest -q --ignore=tests/test_qloo_integration.py
	cd apps/web && npm run lint
	cd apps/web && npm run typecheck

build:
	cd apps/web && npm run build

docker-config:
	docker compose config

docker-up:
	docker compose up --build -d

docker-dev:
	docker compose -f docker-compose.dev.yml up --build -d

docker-down:
	docker compose down

check-qloo:
	cd apps/api && $(ROOT_PY) -m app.cli check-qloo
