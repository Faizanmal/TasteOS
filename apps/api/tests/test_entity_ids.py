"""Unit tests for Qloo entity ID filtering and live signal resolution."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.candidate_retriever import (
    CulturalCandidateRetriever,
    clear_demo_qloo_id_cache,
)
from app.agents.profile_resolver import ResolvedProfile
from app.core.config import Settings
from app.services.qloo.entity_ids import (
    filter_qloo_entity_ids,
    is_qloo_entity_id,
    skipped_favorites_note,
)
from app.services.qloo.models import QlooEntity


RADIOHEAD_UUID = "11111111-1111-4111-8111-111111111111"
BEYONCE_UUID = "22222222-2222-4222-8222-222222222222"
LOCAL_FAKE = "local-0-radiohead"
DEMO_RADIOHEAD = "demo-artist-radiohead"


def test_is_qloo_entity_id_accepts_uuids():
    assert is_qloo_entity_id(RADIOHEAD_UUID)
    assert is_qloo_entity_id(RADIOHEAD_UUID.upper())
    assert not is_qloo_entity_id("demo-artist-radiohead")
    assert not is_qloo_entity_id(LOCAL_FAKE)
    assert not is_qloo_entity_id("unresolved-radiohead")
    assert not is_qloo_entity_id("AAA")
    assert not is_qloo_entity_id("")
    assert not is_qloo_entity_id(None)


def test_filter_qloo_entity_ids_drops_non_uuids_and_dedupes():
    valid, skipped = filter_qloo_entity_ids(
        [
            RADIOHEAD_UUID,
            LOCAL_FAKE,
            "demo-tv-the-bear",
            RADIOHEAD_UUID,
            BEYONCE_UUID,
            "unresolved-x",
            "",
            None,
        ]
    )
    assert valid == [RADIOHEAD_UUID, BEYONCE_UUID]
    assert skipped == 5


def test_skipped_favorites_note():
    assert skipped_favorites_note(0) is None
    assert skipped_favorites_note(-1) is None
    note_one = skipped_favorites_note(1)
    assert note_one is not None
    assert "1 favorite" in note_one
    assert "will not influence recommendations" in note_one
    note_many = skipped_favorites_note(3)
    assert note_many is not None
    assert "3 favorites" in note_many


def _live_settings() -> Settings:
    return Settings(
        tasteos_mode="live",
        qloo_api_key="test-key-not-real",
        database_url="sqlite+aiosqlite:///:memory:",
    )


def _profile_with_ids(*entity_ids: str, name: str = "A") -> ResolvedProfile:
    favs = [
        {
            "entity_id": eid,
            "name": "Radiohead" if "radiohead" in eid.lower() else eid,
            "entity_type": "urn:entity:artist",
        }
        for eid in entity_ids
    ]
    return ResolvedProfile(
        id="p1",
        display_name=name,
        favorite_ids=list(entity_ids),
        favorites=favs,
        preferred_domains=["urn:entity:place"],
        exclusions=set(),
        explicit_preferences=[],
    )


@pytest.mark.asyncio
async def test_live_skips_fake_ids_and_notes_without_400():
    clear_demo_qloo_id_cache()
    settings = _live_settings()
    retriever = CulturalCandidateRetriever(settings)
    profiles = [_profile_with_ids(LOCAL_FAKE, "demo-not-in-seed")]

    place = QlooEntity(
        name="Central Park",
        entity_id="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
        subtype="urn:entity:place",
        query={"affinity": 0.5},
    )

    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.search = AsyncMock(return_value=([], {"status_code": 200}))
    mock_client.insights = AsyncMock(
        return_value=([place], {"status_code": 200, "elapsed_ms": 1})
    )

    with patch(
        "app.agents.candidate_retriever.QlooClient",
        return_value=mock_client,
    ):
        result = await retriever.retrieve(
            profiles,
            target_domain="urn:entity:place",
            location_query="New York",
            take=5,
        )

    assert result.mode == "live"
    step = result.steps[0]
    assert step["source"] == "qloo_insights"
    assert step["signal_entity_count"] == 0
    assert step["skipped_favorite_count"] == 2
    assert any("Skipped 2 favorites" in lim for lim in result.limitations)

    # Insights called with location only — no invalid entity IDs.
    kwargs = mock_client.insights.await_args.kwargs
    assert kwargs["entity_ids"] is None
    assert kwargs["location_query"] == "New York"


@pytest.mark.asyncio
async def test_live_resolves_demo_favorites_to_uuids():
    clear_demo_qloo_id_cache()
    settings = _live_settings()
    retriever = CulturalCandidateRetriever(settings)
    profiles = [
        ResolvedProfile(
            id="demo-profile-maya",
            display_name="Maya",
            favorite_ids=[DEMO_RADIOHEAD],
            favorites=[
                {
                    "entity_id": DEMO_RADIOHEAD,
                    "name": "Radiohead",
                    "entity_type": "urn:entity:artist",
                }
            ],
            preferred_domains=["urn:entity:place"],
            exclusions=set(),
            explicit_preferences=[],
            is_demo=True,
        )
    ]

    seed = QlooEntity(
        name="Radiohead",
        entity_id=RADIOHEAD_UUID,
        subtype="urn:entity:artist",
    )
    place = QlooEntity(
        name="Momofuku",
        entity_id="bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
        subtype="urn:entity:place",
        query={"affinity": 0.7},
    )

    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.search = AsyncMock(return_value=([seed], {"status_code": 200}))
    mock_client.insights = AsyncMock(
        return_value=([place], {"status_code": 200, "elapsed_ms": 2})
    )

    with patch(
        "app.agents.candidate_retriever.QlooClient",
        return_value=mock_client,
    ):
        result = await retriever.retrieve(
            profiles,
            target_domain="urn:entity:place",
            location_query="New York",
            take=5,
        )

    assert result.mode == "live"
    step = result.steps[0]
    assert step["source"] == "qloo_insights"
    assert step["signal_entity_count"] == 1
    assert step["skipped_favorite_count"] == 0
    assert not any("Skipped" in lim for lim in result.limitations)

    kwargs = mock_client.insights.await_args.kwargs
    assert kwargs["entity_ids"] == [RADIOHEAD_UUID]
    mock_client.search.assert_awaited()
    # Second retrieve should hit cache (still one search call total).
    with patch(
        "app.agents.candidate_retriever.QlooClient",
        return_value=mock_client,
    ):
        await retriever.retrieve(
            profiles,
            target_domain="urn:entity:place",
            location_query="New York",
            take=5,
        )
    assert mock_client.search.await_count == 1


@pytest.mark.asyncio
async def test_live_keeps_real_uuids_and_skips_local():
    clear_demo_qloo_id_cache()
    settings = _live_settings()
    retriever = CulturalCandidateRetriever(settings)
    profiles = [_profile_with_ids(RADIOHEAD_UUID, LOCAL_FAKE)]

    place = QlooEntity(
        name="Place",
        entity_id="cccccccc-cccc-4ccc-8ccc-cccccccccccc",
        subtype="urn:entity:place",
    )
    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.insights = AsyncMock(
        return_value=([place], {"status_code": 200, "elapsed_ms": 1})
    )

    with patch(
        "app.agents.candidate_retriever.QlooClient",
        return_value=mock_client,
    ):
        result = await retriever.retrieve(
            profiles,
            target_domain="urn:entity:place",
            location_query=None,
            take=3,
        )

    assert result.steps[0]["signal_entity_count"] == 1
    assert result.steps[0]["skipped_favorite_count"] == 1
    assert any("Skipped 1 favorite" in lim for lim in result.limitations)
    assert mock_client.insights.await_args.kwargs["entity_ids"] == [RADIOHEAD_UUID]
