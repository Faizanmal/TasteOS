# TasteOS API

FastAPI backend — anonymous profiles, Qloo-backed recommendations, Group Concierge.

```bash
# from repo root
python -m venv .venv
.\.venv\Scripts\Activate.ps1   # Windows PowerShell
# source .venv/bin/activate    # Unix
pip install -e "apps/api[dev]"
cp .env.example .env
cd apps/api
uvicorn app.main:app --reload --port 8000
```

OpenAPI: http://localhost:8000/docs · Health: http://localhost:8000/health

```bash
python -m app.cli mode
python -m app.cli check-qloo
alembic upgrade head
pytest -q --ignore=tests/test_qloo_integration.py
```

## Layout

| Path | Role |
| --- | --- |
| `app/api/routes.py` | Versioned REST (`/api/v1/...`) |
| `app/services/profiles` | Profile CRUD + reset |
| `app/services/recommendations` | Validate → Qloo/demo → normalize → persist |
| `app/services/qloo` | Verified Qloo client + demo dataset |
| `app/repositories` | SQLAlchemy persistence |
| `app/core/errors.py` | Centralized HTTP error mapping |
| `alembic/` | Migrations (`taste_profiles`, `recommendations`) |

Persistence uses PostgreSQL (`DATABASE_URL`), configured via Docker Compose (`docker-compose.yml`) or external Postgres.

Contracts and example requests: [docs/API.md](../../docs/API.md).
