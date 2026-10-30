"""Unit tests for deterministic negotiation scoring."""

from __future__ import annotations

from app.agents.candidate_retriever import RetrievedCandidate
from app.agents.negotiation import NegotiationEngine
from app.agents.profile_resolver import ResolvedProfile
from app.services.qloo.models import QlooEntity, QlooTag


def _profile(
    pid: str, name: str, exclusions: list[str] | None = None
) -> ResolvedProfile:
    return ResolvedProfile(
        id=pid,
        display_name=name,
        favorite_ids=["demo-tv-the-bear"],
        favorites=[
            {
                "entity_id": "demo-tv-the-bear",
                "name": "The Bear",
                "entity_type": "urn:entity:tv_show",
            }
        ],
        preferred_domains=["urn:entity:place"],
        exclusions=set(exclusions or []),
        explicit_preferences=["comfort food"],
    )


def _cand(eid: str, name: str, tags: list[str]) -> RetrievedCandidate:
    entity = QlooEntity(
        name=name,
        entity_id=eid,
        subtype="urn:entity:place",
        tags=[QlooTag(name=t) for t in tags],
        query={"affinity": 0.5},
    )
    return RetrievedCandidate(
        entity=entity,
        source="tasteos_demo_dataset",
        qloo_affinity=None,
        meta={},
    )


def test_exclusion_zeroes_participant():
    engine = NegotiationEngine()
    profiles = [
        _profile("a", "A"),
        _profile("b", "B", exclusions=["place-1"]),
    ]
    result = engine.rank(
        [_cand("place-1", "Excluded Place", ["Italian"])], profiles, mode="demo"
    )
    match_b = next(
        m for m in result.ranked[0].participant_matches if m.profile_id == "b"
    )
    assert match_b.status == "excluded"
    assert match_b.app_score == 0.0


def test_ranking_is_deterministic():
    engine = NegotiationEngine()
    profiles = [_profile("a", "A"), _profile("b", "B")]
    cands = [
        _cand("p2", "Beta", ["Cafe"]),
        _cand("p1", "Alpha", ["Italian", "Comfort"]),
    ]
    r1 = engine.rank(cands, profiles, mode="demo")
    r2 = engine.rank(cands, profiles, mode="demo")
    assert [c.entity_id for c in r1.ranked] == [c.entity_id for c in r2.ranked]
    assert [c.app_rank_score for c in r1.ranked] == [
        c.app_rank_score for c in r2.ranked
    ]


def test_demo_does_not_set_qloo_affinity():
    engine = NegotiationEngine()
    result = engine.rank(
        [_cand("p1", "Place", ["French"])],
        [_profile("a", "A")],
        mode="demo",
    )
    assert result.ranked[0].qloo_affinity is None
    assert result.ranked[0].source == "tasteos_demo_dataset"
