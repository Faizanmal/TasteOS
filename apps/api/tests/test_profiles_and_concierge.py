"""Profile CRUD and Group Concierge demo-mode tests."""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_health(client):
    res = await client.get("/health")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert body["mode"] == "demo"
    assert (
        "qloo_api_key" not in str(body).lower() or body["qloo_key_configured"] is False
    )


@pytest.mark.asyncio
async def test_mode_indicator(client):
    res = await client.get("/api/v1/mode")
    assert res.status_code == 200
    assert res.json()["mode"] == "demo"
    assert "NOT from a live Qloo" in res.json()["description"]


@pytest.mark.asyncio
async def test_demo_profiles(client):
    res = await client.get("/api/v1/profiles/demo")
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 3
    assert all(p["is_demo"] for p in data)


@pytest.mark.asyncio
async def test_profile_crud(client):
    create = await client.post(
        "/api/v1/profiles",
        json={
            "display_name": "Alex",
            "favorites": [
                {
                    "entity_id": "demo-movie-parasite",
                    "name": "Parasite",
                    "entity_type": "urn:entity:movie",
                }
            ],
            "exclusions": [],
            "explicit_preferences": ["spicy food"],
        },
    )
    assert create.status_code == 201
    profile = create.json()
    pid = profile["id"]

    got = await client.get(f"/api/v1/profiles/{pid}")
    assert got.status_code == 200
    assert got.json()["display_name"] == "Alex"

    patched = await client.patch(
        f"/api/v1/profiles/{pid}",
        json={"display_name": "Alexandra"},
    )
    assert patched.status_code == 200
    assert patched.json()["display_name"] == "Alexandra"

    deleted = await client.delete(f"/api/v1/profiles/{pid}")
    assert deleted.status_code == 204
    missing = await client.get(f"/api/v1/profiles/{pid}")
    assert missing.status_code == 404


@pytest.mark.asyncio
async def test_demo_profiles_readonly(client):
    res = await client.patch(
        "/api/v1/profiles/demo-profile-maya",
        json={"display_name": "Nope"},
    )
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_concierge_plan_and_reject(client, demo_profile_ids):
    res = await client.post(
        "/api/v1/concierge/plan",
        json={
            "profile_ids": demo_profile_ids,
            "target_domain": "urn:entity:place",
            "location_query": "New York",
            "experience": "evening_out",
            "take": 6,
        },
    )
    assert res.status_code == 200
    plan = res.json()
    assert plan["mode"] == "demo"
    assert plan["primary"]["source"] == "tasteos_demo_dataset"
    assert plan["primary"]["qloo_affinity"] is None
    assert "pipeline" in plan and len(plan["pipeline"]) >= 3
    assert any(s["stage"] == "negotiate" for s in plan["pipeline"])
    # Scores are application logic
    assert "app_rank_score" in plan["primary"]
    assert plan["primary"]["ranking_inputs"]["method"] == "tasteos_negotiation_v1"

    rejected_id = plan["primary"]["entity_id"]
    regen = await client.post(
        f"/api/v1/concierge/plan/{plan['id']}/reject",
        params={"entity_id": rejected_id},
    )
    assert regen.status_code == 200
    new_plan = regen.json()
    assert new_plan["primary"]["entity_id"] != rejected_id
    assert rejected_id in new_plan["rejected_entity_ids"]


@pytest.mark.asyncio
async def test_exclusion_removes_candidate(client, demo_profile_ids):
    res = await client.post(
        "/api/v1/recommendations",
        json={
            "profile_ids": demo_profile_ids,
            "target_domain": "urn:entity:place",
            "location_query": "New York",
            "exclusions": ["demo-place-balthazar"],
            "take": 10,
        },
    )
    assert res.status_code == 200
    ids = [c["entity_id"] for c in res.json()["candidates"]]
    assert "demo-place-balthazar" not in ids


@pytest.mark.asyncio
async def test_demo_search(client):
    res = await client.get("/api/v1/search", params={"query": "Radiohead"})
    assert res.status_code == 200
    body = res.json()
    assert body["mode"] == "demo"
    assert body["source"] == "tasteos_demo_dataset"
    assert any(r["name"] == "Radiohead" for r in body["results"])


@pytest.mark.asyncio
async def test_unknown_evidence_not_fabricated(client, demo_profile_ids):
    res = await client.post(
        "/api/v1/recommendations",
        json={
            "profile_ids": demo_profile_ids,
            "target_domain": "urn:entity:place",
            "location_query": "New York",
            "take": 5,
        },
    )
    body = res.json()
    # Every participant match must use allowed statuses; unknown is allowed
    for cand in body["candidates"]:
        for match in cand["participant_matches"]:
            assert match["status"] in {"supported", "unknown", "conflict", "excluded"}
            if match["status"] == "unknown":
                assert match["app_score"] is None
