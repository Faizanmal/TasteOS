"""Shared pytest fixtures."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

_RUN_LIVE = os.environ.get("TASTEOS_RUN_LIVE_QLOO", "").lower() in {"1", "true", "yes"}

# Unit tests default to demo mode. Live integration opts in via TASTEOS_RUN_LIVE_QLOO=1
# so this conftest does not wipe credentials for that run.
if not _RUN_LIVE:
    os.environ["TASTEOS_MODE"] = "demo"
    os.environ["QLOO_API_KEY"] = ""
else:
    os.environ.setdefault("TASTEOS_MODE", "live")
    # If the process env lacks a key, load from the nearest .env without printing it.
    if not os.environ.get("QLOO_API_KEY", "").strip():
        for candidate in (Path(__file__).resolve().parents[3] / ".env", Path(".env")):
            if not candidate.exists():
                continue
            for line in candidate.read_text(encoding="utf-8").splitlines():
                if line.startswith("QLOO_API_KEY=") and line.split("=", 1)[1].strip():
                    os.environ["QLOO_API_KEY"] = line.split("=", 1)[1].strip()
                    break
            if os.environ.get("QLOO_API_KEY", "").strip():
                break

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ.setdefault("FRONTEND_URL", "http://localhost:3000")

from app.core.config import get_settings
from app.core.database import Base, get_db
from app.main import app

get_settings.cache_clear()


@pytest_asyncio.fixture
async def client():
    get_settings.cache_clear()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async def override_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
    await engine.dispose()
    get_settings.cache_clear()


@pytest.fixture
def demo_profile_ids() -> list[str]:
    return [
        "demo-profile-maya",
        "demo-profile-jordan",
        "demo-profile-sam",
    ]
