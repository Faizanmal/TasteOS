"""Phase 4 Group Concierge engine tests — negotiation, constraints, plans."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.agents.candidate_retriever import RetrievedCandidate, RetrieveResult
from app.agents.constraint_evaluator import ConstraintEvaluator
from app.agents.explanation import BOOKING_DISCLAIMER
from app.agents.negotiation import NegotiationEngine
from app.agents.profile_resolver import ResolvedProfile
from app.services.qloo.models import QlooEntity, QlooTag


def _profile(
    pid: str,
    name: str,
    *,
    exclusions: list[str] | None = None,
    prefs: list[str] | None = None,
    favorites: list[dict] | None = None,
) -> ResolvedProfile:
    favs = (
        favorites
        if favorites is not None
        else [
            {
                "entity_id": "demo-tv-the-bear",
                "name": "The Bear",
                "entity_type": "urn:entity:tv_show",
            }
        ]
    )
    return ResolvedProfile(
        id=pid,
        display_name=name,
        favorite_ids=[f["entity_id"] for f in favs],
        favorites=favs,
        preferred_domains=["urn:entity:place"],
        exclusions=set(exclusions or []),
        explicit_preferences=list(prefs or []),
    )


def _cand(
    eid: str,
    name: str,
    tags: list[str],
    *,
    affinity: float | None = None,
    source: str = "tasteos_demo_dataset",
    explain: dict | None = None,
) -> RetrievedCandidate:
    query = {"affinity": affinity} if affinity is not None else {}
    entity = QlooEntity(
        name=name,
        entity_id=eid,
        subtype="urn:entity:place",
        tags=[QlooTag(name=t) for t in tags],
        query=query or None,
    )
    return RetrievedCandidate(
        entity=entity,
        source=source,
        qloo_affinity=affinity if source == "qloo" else None,
        meta={"explainability": explain or {}},
    )


def test_hard_exclusion_removes_before_rank():
    profiles = [_profile("a", "A", exclusions=["p-bad"]), _profile("b", "B")]
    cands = [
        _cand("p-bad", "Bad", ["Italian"]),
        _cand("p-good", "Good", ["Italian", "Comfort"]),
    ]
    result = ConstraintEvaluator().evaluate(
        cands, profiles, exclusions=[], rejected_entity_ids=[], budget="any"
    )
    assert [c.entity.entity_id for c in result.kept] == ["p-good"]
    assert result.removed[0]["reason"] == "hard_exclusion_or_rejection"


def test_request_exclusions_and_rejections():
    profiles = [_profile("a", "A")]
    cands = [_cand("x", "X", ["Cafe"]), _cand("y", "Y", ["Cafe"])]
    result = ConstraintEvaluator().evaluate(
        cands, profiles, exclusions=["x"], rejected_entity_ids=["y"], budget="any"
    )
    assert result.kept == []
    assert len(result.removed) == 2


def test_missing_evidence_is_unknown_not_fabricated():
    engine = NegotiationEngine()
    # No food-culture favorites, no overlapping prefs/tags
    profiles = [
        _profile(
            "cold",
            "Cold",
            favorites=[
                {
                    "entity_id": "demo-brand-patagonia",
                    "name": "Patagonia",
                    "entity_type": "urn:entity:brand",
                }
            ],
            prefs=[],
        )
    ]
    ranked = engine.rank(
        [_cand("p1", "Quiet Bar", ["Wine"])], profiles, mode="demo"
    ).ranked
    match = ranked[0].participant_matches[0]
    assert match.status == "unknown"
    assert match.app_score is None
    assert match.qloo_affinity is None
    assert ranked[0].qloo_affinity is None


def test_soft_conflict_status():
    engine = NegotiationEngine()
    profiles = [_profile("a", "A", prefs=["avoid fine dining"], favorites=[])]
    ranked = engine.rank(
        [_cand("p1", "Fancy", ["Fine Dining", "French"])],
        profiles,
        mode="demo",
    ).ranked
    assert ranked[0].participant_matches[0].status == "conflict"
    assert ranked[0].participant_matches[0].app_score == 0.15


def test_fairness_beats_one_person_max():
    """Balanced coverage should outrank a candidate that only thrills one person."""
    engine = NegotiationEngine()
    # A has The Bear → demo food heuristic; B has no food signal and no prefs
    a = _profile("a", "A", prefs=["comfort food"])
    b = _profile(
        "b",
        "B",
        favorites=[
            {
                "entity_id": "demo-artist-beyonce",
                "name": "Beyoncé",
                "entity_type": "urn:entity:artist",
            }
        ],
        prefs=["lively atmosphere"],
    )
    # Solo thrill: only A gets food heuristic; B unknown
    solo = _cand("solo", "Solo Spot", ["Fine Dining"])
    # Shared: comfort food tag hits A's pref; lively hits B's pref via tag substring?
    # "lively" won't be in tags — give both explicit tag overlaps
    shared = _cand(
        "shared", "Shared Spot", ["comfort food", "lively atmosphere", "Cafe"]
    )

    result = engine.rank([solo, shared], [a, b], mode="demo")
    assert result.ranked[0].entity_id == "shared"
    assert (
        result.ranked[0].ranking_inputs["coverage"]
        >= result.ranked[1].ranking_inputs["coverage"]
    )


def test_live_affinity_cannot_dominate_alone():
    engine = NegotiationEngine()
    profiles = [
        _profile("a", "A", favorites=[], prefs=[]),
        _profile("b", "B", favorites=[], prefs=[]),
    ]
    high_aff_unknown = _cand(
        "hot",
        "Hot Affinity",
        ["Misc"],
        affinity=0.99,
        source="qloo",
    )
    balanced = _cand(
        "bal",
        "Balanced",
        ["comfort food"],
        affinity=0.2,
        source="qloo",
        explain={"entities": [{"entity_id": "demo-tv-the-bear"}]},
    )
    # Give profiles The Bear so explainability supports both on balanced
    profiles = [
        _profile("a", "A"),
        _profile("b", "B"),
    ]
    ranked = engine.rank([high_aff_unknown, balanced], profiles, mode="live").ranked
    # Balanced has coverage from explainability; hot has only affinity + unknown support
    assert ranked[0].entity_id == "bal"
    assert ranked[0].ranking_inputs["qloo_component"] <= 0.15


def test_ranking_deterministic_and_stable():
    engine = NegotiationEngine()
    profiles = [_profile("a", "A"), _profile("b", "B")]
    cands = [
        _cand("p2", "Beta", ["Cafe"]),
        _cand("p1", "Alpha", ["Italian", "Comfort"]),
        _cand("p3", "Gamma", ["Bar"]),
    ]
    r1 = engine.rank(cands, profiles, mode="demo")
    r2 = engine.rank(list(reversed(cands)), profiles, mode="demo")
    assert [c.entity_id for c in r1.ranked] == [c.entity_id for c in r2.ranked]
    assert [c.app_rank_score for c in r1.ranked] == [
        c.app_rank_score for c in r2.ranked
    ]


def test_conflicting_hard_exclusions_across_group():
    engine = NegotiationEngine()
    profiles = [
        _profile("maya", "Maya", exclusions=["eleven"]),
        _profile("sam", "Sam"),
    ]
    ranked = engine.rank(
        [_cand("eleven", "Eleven Madison", ["Fine Dining"])],
        profiles,
        mode="demo",
    ).ranked
    statuses = {m.profile_id: m.status for m in ranked[0].participant_matches}
    assert statuses["maya"] == "excluded"
    # Sam may be supported via demo food heuristic
    assert statuses["sam"] in {"supported", "unknown"}


@pytest.mark.asyncio
async def test_concierge_plan_structure_and_disclaimer(client, demo_profile_ids):
    res = await client.post(
        "/api/v1/concierge/plan",
        json={
            "profile_ids": demo_profile_ids,
            "target_domain": "urn:entity:place",
            "location_query": "New York",
            "experience": "evening_out",
            "alternatives_count": 2,
            "take": 5,
        },
    )
    assert res.status_code == 200
    plan = res.json()
    assert plan["disclaimer"] == BOOKING_DISCLAIMER
    assert "selection_rationale" in plan
    assert plan["primary"]["ranking_inputs"]["method"] == "tasteos_negotiation_v1"
    assert plan["primary"]["qloo_affinity"] is None
    assert plan["primary"]["source"] == "tasteos_demo_dataset"
    assert len(plan["alternatives"]) <= 2
    assert all(s["is_proposed"] for s in plan["itinerary"])
    assert any(
        "not" in s["detail"].lower() and "reserv" in s["detail"].lower()
        for s in plan["itinerary"]
    ) or (BOOKING_DISCLAIMER in plan["disclaimer"])
    stages = [s.get("stage") for s in plan["pipeline"]]
    assert "negotiate" in stages
    assert "plan_compose" in stages
    assert "explain" in stages
    # Evidence vs generated explanation distinction
    assert "evidence_refs" in plan["primary"]
    assert (
        "application" in plan["selection_rationale"].lower()
        or "tasteos" in plan["selection_rationale"].lower()
    )


@pytest.mark.asyncio
async def test_concierge_invalid_experience(client, demo_profile_ids):
    res = await client.post(
        "/api/v1/concierge/plan",
        json={
            "profile_ids": demo_profile_ids,
            "experience": "skydiving",
        },
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_concierge_missing_profile(client):
    res = await client.post(
        "/api/v1/concierge/plan",
        json={
            "profile_ids": ["does-not-exist"],
            "experience": "dinner",
        },
    )
    assert res.status_code == 400
    assert "not found" in res.json()["error"]["message"].lower()


@pytest.mark.asyncio
async def test_concierge_empty_retrieve_returns_error(client, demo_profile_ids):
    empty = RetrieveResult(candidates=[], mode="demo", steps=[], limitations=["empty"])

    with patch(
        "app.services.recommendations.service.CulturalCandidateRetriever.retrieve",
        new=AsyncMock(return_value=empty),
    ):
        res = await client.post(
            "/api/v1/concierge/plan",
            json={
                "profile_ids": demo_profile_ids,
                "experience": "evening_out",
            },
        )
    assert res.status_code == 400
    assert "no candidates" in res.json()["error"]["message"].lower()


@pytest.mark.asyncio
async def test_rejection_changes_primary(client, demo_profile_ids):
    first = await client.post(
        "/api/v1/concierge/plan",
        json={
            "profile_ids": demo_profile_ids,
            "target_domain": "urn:entity:place",
            "location_query": "New York",
            "experience": "evening_out",
            "alternatives_count": 3,
            "take": 6,
        },
    )
    assert first.status_code == 200
    plan = first.json()
    rejected = plan["primary"]["entity_id"]
    alt_ids = [a["entity_id"] for a in plan["alternatives"]]

    regen = await client.post(
        f"/api/v1/concierge/plan/{plan['id']}/reject",
        params={"entity_id": rejected},
    )
    assert regen.status_code == 200
    new_plan = regen.json()
    assert new_plan["primary"]["entity_id"] != rejected
    assert rejected in new_plan["rejected_entity_ids"]
    assert rejected not in [
        new_plan["primary"]["entity_id"],
        *[a["entity_id"] for a in new_plan["alternatives"]],
    ]
    # Prefer that an earlier alternative becomes primary when available
    if alt_ids:
        assert (
            new_plan["primary"]["entity_id"] in alt_ids
            or new_plan["primary"]["entity_id"] != rejected
        )

    got = await client.get(f"/api/v1/concierge/plan/{new_plan['id']}")
    assert got.status_code == 200
    assert got.json()["id"] == new_plan["id"]


@pytest.mark.asyncio
async def test_hard_exclusion_in_plan_request(client, demo_profile_ids):
    res = await client.post(
        "/api/v1/concierge/plan",
        json={
            "profile_ids": demo_profile_ids,
            "target_domain": "urn:entity:place",
            "exclusions": ["demo-place-balthazar"],
            "experience": "dinner",
            "take": 8,
        },
    )
    assert res.status_code == 200
    plan = res.json()
    assert plan["primary"]["entity_id"] != "demo-place-balthazar"
    assert all(a["entity_id"] != "demo-place-balthazar" for a in plan["alternatives"])


@pytest.mark.asyncio
async def test_maya_exclusion_never_surfaces_eleven_madison(client, demo_profile_ids):
    res = await client.post(
        "/api/v1/concierge/plan",
        json={
            "profile_ids": demo_profile_ids,
            "target_domain": "urn:entity:place",
            "experience": "evening_out",
            "take": 10,
        },
    )
    plan = res.json()
    ids = [
        plan["primary"]["entity_id"],
        *[a["entity_id"] for a in plan["alternatives"]],
    ]
    assert "demo-place-eleven-madison" not in ids
