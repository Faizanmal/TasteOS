"""Live Qloo integration test — opt in explicitly to avoid accidental quota burn.

Mocked unit tests do NOT satisfy this module. This file hits the real hackathon host.

Run:
  $env:TASTEOS_RUN_LIVE_QLOO='1'
  # QLOO_API_KEY from process env or repo-root .env (never commit the key)
  pytest -m integration -q tests/test_qloo_integration.py
"""

from __future__ import annotations

import os

import pytest

from app.core.config import Settings
from app.services.qloo.client import HACKATHON_BASE_URL, QlooClient

pytestmark = pytest.mark.integration


def _live_settings() -> Settings | None:
    if os.environ.get("TASTEOS_RUN_LIVE_QLOO", "").lower() not in {"1", "true", "yes"}:
        return None
    key = os.environ.get("QLOO_API_KEY", "").strip()
    if not key:
        return None
    return Settings(
        tasteos_mode="live",
        qloo_api_key=key,
        qloo_base_url=os.environ.get("QLOO_BASE_URL", HACKATHON_BASE_URL),
    )


@pytest.mark.asyncio
async def test_live_qloo_search_and_insights():
    settings = _live_settings()
    if settings is None:
        pytest.skip(
            "Set TASTEOS_RUN_LIVE_QLOO=1 with QLOO_API_KEY available "
            "(process env or repo-root .env). "
            "Unit tests with MockTransport do not prove live connectivity."
        )

    assert "hackathon.api.qloo.com" in settings.qloo_base_url

    async with QlooClient(settings) as client:
        entities, meta = await client.search(
            "Radiohead", types=["urn:entity:artist"], take=3
        )
        assert meta["status_code"] in {200, 404}
        assert meta["source"] == "qloo"
        assert isinstance(entities, list)

        if not entities:
            pytest.skip(
                "Live search returned no entities for Radiohead; cannot continue insights"
            )

        eid = entities[0].entity_id
        assert eid
        insights, imeta = await client.insights(
            filter_type="urn:entity:place",
            entity_ids=[eid],
            location_query="New York",
            take=5,
        )
        assert imeta["status_code"] == 200
        assert imeta["source"] == "qloo"
        assert isinstance(insights, list)
        for entity in insights:
            affinity = entity.affinity_from_query()
            assert affinity is None or isinstance(affinity, float)
