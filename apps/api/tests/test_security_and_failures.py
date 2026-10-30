"""Security and failure-scenario tests for TasteOS Core / Concierge."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.exc import OperationalError

from app.agents.candidate_retriever import RetrieveResult
from app.core.config import get_settings
from app.core.logging import redact
from app.main import app
from app.services.qloo.client import QlooError, QlooTransientError


def test_redact_masks_api_keys():
    raw = "upstream failed qloo_api_key=super-secret-value-123 Authorization: Bearer abc.def"
    cleaned = redact(raw)
    assert "super-secret-value-123" not in cleaned
    assert "abc.def" not in cleaned
    assert "[REDACTED]" in cleaned


@pytest.mark.asyncio
async def test_health_and_mode_never_expose_secret(client):
    health = await client.get("/health")
    mode = await client.get("/api/v1/mode")
    blob = (health.text + mode.text).lower()
    assert "qloo_api_key" not in blob or '"qloo_key_configured"' in health.text.lower()
    assert "bearer" not in blob
    assert health.json()["qloo_key_configured"] in {True, False}
    assert (
        "key" not in str(mode.json().get("description", "")).lower()
        or "not" in mode.json()["description"].lower()
    )


@pytest.mark.asyncio
async def test_invalid_profile_payload_422(client):
    res = await client.post("/api/v1/profiles", json={"display_name": ""})
    assert res.status_code == 422
    body = res.json()
    assert body["error"]["code"] == "request_validation"
    assert "api_key" not in res.text.lower()


@pytest.mark.asyncio
async def test_concierge_invalid_experience_422(client, demo_profile_ids):
    res = await client.post(
        "/api/v1/concierge/plan",
        json={"profile_ids": demo_profile_ids, "experience": "not-a-real-experience"},
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_qloo_upstream_error_safe_body(client, demo_profile_ids):
    async def boom(*_a, **_k):
        raise QlooError("qloo_api_key=should-not-leak refused", status_code=502)

    with patch(
        "app.services.recommendations.service.CulturalCandidateRetriever.retrieve",
        new=AsyncMock(side_effect=boom),
    ):
        res = await client.post(
            "/api/v1/recommendations",
            json={
                "profile_ids": demo_profile_ids,
                "target_domain": "urn:entity:place",
                "take": 3,
            },
        )
    assert res.status_code == 502
    assert res.json()["error"]["code"] == "qloo_upstream"
    assert "should-not-leak" not in res.text


@pytest.mark.asyncio
async def test_qloo_timeout_maps_to_upstream(client, demo_profile_ids):
    async def boom(*_a, **_k):
        raise QlooTransientError("timeout talking to Qloo", status_code=504)

    with patch(
        "app.services.recommendations.service.CulturalCandidateRetriever.retrieve",
        new=AsyncMock(side_effect=boom),
    ):
        res = await client.post(
            "/api/v1/recommendations",
            json={
                "profile_ids": demo_profile_ids,
                "target_domain": "urn:entity:place",
                "take": 3,
            },
        )
    assert res.status_code == 504
    assert res.json()["error"]["code"] == "qloo_upstream"


@pytest.mark.asyncio
async def test_empty_candidates_concierge_400(client, demo_profile_ids):
    empty = RetrieveResult(candidates=[], mode="demo", steps=[], limitations=["empty"])
    with patch(
        "app.services.recommendations.service.CulturalCandidateRetriever.retrieve",
        new=AsyncMock(return_value=empty),
    ):
        res = await client.post(
            "/api/v1/concierge/plan",
            json={"profile_ids": demo_profile_ids, "experience": "evening_out"},
        )
    assert res.status_code == 400
    assert "no candidates" in res.json()["error"]["message"].lower()


@pytest.mark.asyncio
async def test_database_error_503(client):
    with patch(
        "app.repositories.profiles.ProfileRepository.create",
        new=AsyncMock(
            side_effect=OperationalError("SELECT 1", {}, Exception("db down")),
        ),
    ):
        res = await client.post(
            "/api/v1/profiles",
            json={"display_name": "Temp"},
        )
    assert res.status_code == 503
    assert res.json()["error"]["code"] == "database_unavailable"


@pytest.mark.asyncio
async def test_live_mode_without_key_rejected(monkeypatch):
    monkeypatch.setenv("TASTEOS_MODE", "live")
    monkeypatch.setenv("QLOO_API_KEY", "")
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    get_settings.cache_clear()
    try:
        with pytest.raises(RuntimeError, match="QLOO_API_KEY"):
            get_settings()
    finally:
        monkeypatch.setenv("TASTEOS_MODE", "demo")
        get_settings.cache_clear()


@pytest.mark.asyncio
async def test_cors_allowlist_reflects_frontend(client):
    res = await client.options(
        "/api/v1/mode",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert res.status_code in {200, 204}
    assert res.headers.get("access-control-allow-origin") == "http://localhost:3000"


@pytest.mark.asyncio
async def test_cors_unknown_origin_not_reflected():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.options(
            "/api/v1/mode",
            headers={
                "Origin": "https://evil.example",
                "Access-Control-Request-Method": "GET",
            },
        )
    # Starlette omits ACAO for disallowed origins
    assert res.headers.get("access-control-allow-origin") != "https://evil.example"


@pytest.mark.asyncio
async def test_oversized_body_rejected(client):
    huge = "x" * 1_000_001
    res = await client.post(
        "/api/v1/profiles",
        content=f'{{"display_name":"{huge}"}}',
        headers={"Content-Type": "application/json", "Content-Length": str(1_000_100)},
    )
    assert res.status_code == 413
