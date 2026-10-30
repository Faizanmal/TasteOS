"""Phase 3 TasteOS Core API tests — profiles, recommendations, errors."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.services.qloo.client import QlooError


@pytest.mark.asyncio
async def test_profile_reset_clears_taste_fields(client):
    create = await client.post(
        "/api/v1/profiles",
        json={
            "display_name": "ResetMe",
            "favorites": [
                {
                    "entity_id": "demo-movie-parasite",
                    "name": "Parasite",
                    "entity_type": "urn:entity:movie",
                }
            ],
            "preferred_domains": ["urn:entity:place"],
            "exclusions": ["loud bars"],
            "explicit_preferences": ["spicy"],
            "notes": "temporary",
        },
    )
    assert create.status_code == 201
    pid = create.json()["id"]

    reset = await client.post(f"/api/v1/profiles/{pid}/reset")
    assert reset.status_code == 200
    body = reset.json()
    assert body["id"] == pid
    assert body["display_name"] == "ResetMe"
    assert body["favorites"] == []
    assert body["preferred_domains"] == []
    assert body["exclusions"] == []
    assert body["explicit_preferences"] == []
    assert body["notes"] is None


@pytest.mark.asyncio
async def test_profile_reset_demo_forbidden(client):
    res = await client.post("/api/v1/profiles/demo-profile-maya/reset")
    assert res.status_code == 403
    assert res.json()["error"]["code"] == "forbidden"


@pytest.mark.asyncio
async def test_profile_invalid_domain_rejected(client):
    res = await client.post(
        "/api/v1/profiles",
        json={
            "display_name": "BadDomain",
            "preferred_domains": ["urn:entity:music"],
        },
    )
    assert res.status_code == 400
    assert "preferred_domains" in res.json()["error"]["message"]


@pytest.mark.asyncio
async def test_recommendation_invalid_domain_422(client, demo_profile_ids):
    res = await client.post(
        "/api/v1/recommendations",
        json={
            "profile_ids": demo_profile_ids,
            "target_domain": "urn:entity:music",
            "take": 3,
        },
    )
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "request_validation"


@pytest.mark.asyncio
async def test_recommendation_persist_and_get(client, demo_profile_ids):
    create = await client.post(
        "/api/v1/recommendations",
        json={
            "profile_ids": demo_profile_ids,
            "target_domain": "urn:entity:place",
            "location_query": "New York",
            "take": 3,
        },
    )
    assert create.status_code == 200
    body = create.json()
    assert body["mode"] == "demo"
    assert body["candidates"]
    assert all(c["qloo_affinity"] is None for c in body["candidates"])
    assert all(c["source"] == "tasteos_demo_dataset" for c in body["candidates"])
    assert any(s.get("stage") == "provenance" for s in body["pipeline"])

    got = await client.get(f"/api/v1/recommendations/{body['id']}")
    assert got.status_code == 200
    assert got.json()["id"] == body["id"]


@pytest.mark.asyncio
async def test_recommendation_missing_returns_404(client):
    res = await client.get(
        "/api/v1/recommendations/00000000-0000-0000-0000-000000000000"
    )
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_recommendation_qloo_upstream_error_mapped(client, demo_profile_ids):
    async def boom(*_args, **_kwargs):
        raise QlooError("upstream refused", status_code=401)

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
    assert res.status_code == 401
    payload = res.json()
    assert payload["error"]["code"] == "qloo_upstream"
    assert "api_key" not in str(payload).lower()
    assert "test-key" not in str(payload).lower()


@pytest.mark.asyncio
async def test_openapi_documents_core_paths(client):
    res = await client.get("/openapi.json")
    assert res.status_code == 200
    paths = res.json()["paths"]
    for path in (
        "/api/v1/profiles",
        "/api/v1/profiles/{profile_id}",
        "/api/v1/profiles/{profile_id}/reset",
        "/api/v1/recommendations",
        "/api/v1/recommendations/{recommendation_id}",
    ):
        assert path in paths


@pytest.mark.asyncio
async def test_health_never_leaks_secrets(client):
    res = await client.get("/health")
    assert res.status_code == 200
    raw = res.text.lower()
    assert "qloo_api_key" not in raw
    assert "bearer" not in raw
