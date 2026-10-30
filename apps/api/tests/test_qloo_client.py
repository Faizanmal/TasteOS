"""Qloo client unit tests with mocked HTTP (httpx MockTransport).

These tests prove request construction, parsing, and error handling.
They do NOT prove live Qloo connectivity.
"""

from __future__ import annotations

import httpx
import pytest

from app.core.config import Settings
from app.services.qloo.client import (
    QlooClient,
    QlooError,
    QlooRateLimitError,
    QlooTransientError,
)


def _settings(**kwargs) -> Settings:
    base = {
        "TASTEOS_MODE": "live",
        "QLOO_API_KEY": "test-key-not-real",
        "QLOO_BASE_URL": "https://hackathon.api.qloo.com",
        "QLOO_MAX_RETRIES": 1,
        "QLOO_TIMEOUT_SECONDS": 5,
    }
    base.update(kwargs)
    return Settings(**base)


def _transport(handler):
    return httpx.MockTransport(handler)


@pytest.mark.asyncio
async def test_search_builds_auth_header_and_params():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["headers"] = dict(request.headers)
        captured["url"] = str(request.url)
        assert "authorization" not in {k.lower() for k in request.headers.keys()}
        return httpx.Response(
            200,
            json={
                "success": True,
                "results": [
                    {
                        "name": "Radiohead",
                        "entity_id": "AAA",
                        "subtype": "urn:entity:artist",
                    }
                ],
            },
        )

    client = httpx.AsyncClient(
        transport=_transport(handler),
        base_url="https://hackathon.api.qloo.com",
    )
    async with QlooClient(_settings(), client=client) as qloo:
        entities, meta = await qloo.search(
            "Radiohead", types=["urn:entity:artist"], take=5
        )

    assert captured["headers"].get("x-api-key") == "test-key-not-real"
    assert "query=Radiohead" in captured["url"]
    assert (
        "types=urn%3Aentity%3Aartist" in captured["url"]
        or "types=urn:entity:artist" in captured["url"]
    )
    assert entities[0].name == "Radiohead"
    assert meta["status_code"] == 200
    assert meta["source"] == "qloo"
    await client.aclose()


@pytest.mark.asyncio
async def test_insights_params_place_uses_filter_location_query():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        return httpx.Response(
            200,
            json={
                "success": True,
                "results": {
                    "entities": [
                        {
                            "name": "Balthazar",
                            "entity_id": "BBB",
                            "subtype": "urn:entity:place",
                            "query": {"affinity": 0.9},
                            "properties": {"description": "French brasserie"},
                        }
                    ]
                },
            },
        )

    client = httpx.AsyncClient(
        transport=_transport(handler),
        base_url="https://hackathon.api.qloo.com",
    )
    async with QlooClient(_settings(), client=client) as qloo:
        entities, meta = await qloo.insights(
            filter_type="urn:entity:place",
            entity_ids=["AAA"],
            location_query="New York",
            take=5,
        )
    assert "filter.type=urn%3Aentity%3Aplace" in captured["url"]
    assert (
        "filter.location.query=New%20York" in captured["url"]
        or "filter.location.query=New+York" in captured["url"]
    )
    assert "signal.interests.entities=AAA" in captured["url"]
    assert entities[0].affinity_from_query() == 0.9
    assert meta["source"] == "qloo"
    assert meta["endpoint"] == "/v2/insights"
    await client.aclose()


@pytest.mark.asyncio
async def test_build_insights_rejects_unsupported_type():
    qloo = QlooClient(_settings())
    with pytest.raises(QlooError, match="Unsupported filter.type"):
        qloo.build_insights_params(filter_type="urn:entity:music", entity_ids=["x"])


@pytest.mark.asyncio
async def test_build_insights_requires_signal():
    qloo = QlooClient(_settings())
    with pytest.raises(QlooError, match="at least one documented signal"):
        qloo.build_insights_params(filter_type="urn:entity:movie")


@pytest.mark.asyncio
async def test_401_error_message():
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"message": "unauthorized"})

    client = httpx.AsyncClient(
        transport=_transport(handler),
        base_url="https://hackathon.api.qloo.com",
    )
    async with QlooClient(_settings(), client=client) as qloo:
        with pytest.raises(QlooError, match="authentication"):
            await qloo.insights(
                filter_type="urn:entity:movie",
                entity_ids=["AAA"],
                take=1,
            )
    await client.aclose()


@pytest.mark.asyncio
async def test_rate_limit_then_success():
    calls = {"n": 0}

    def handler(_: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(429, json={"message": "slow down"})
        return httpx.Response(
            200,
            json={
                "results": [
                    {"name": "X", "entity_id": "1", "subtype": "urn:entity:movie"}
                ]
            },
        )

    client = httpx.AsyncClient(
        transport=_transport(handler),
        base_url="https://hackathon.api.qloo.com",
    )
    async with QlooClient(_settings(), client=client) as qloo:
        entities, _ = await qloo.search("X", take=1)
    assert entities[0].name == "X"
    assert calls["n"] == 2
    await client.aclose()


@pytest.mark.asyncio
async def test_timeout_raises_transient():
    def handler(_: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow")

    client = httpx.AsyncClient(
        transport=_transport(handler),
        base_url="https://hackathon.api.qloo.com",
    )
    async with QlooClient(_settings(QLOO_MAX_RETRIES=0), client=client) as qloo:
        with pytest.raises(QlooTransientError, match="timed out"):
            await qloo.search("X", take=1)
    await client.aclose()


@pytest.mark.asyncio
async def test_invalid_json_body():
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, text="not-json", headers={"content-type": "text/plain"}
        )

    client = httpx.AsyncClient(
        transport=_transport(handler),
        base_url="https://hackathon.api.qloo.com",
    )
    async with QlooClient(_settings(), client=client) as qloo:
        with pytest.raises(QlooError, match="non-JSON"):
            await qloo.search("X", take=1)
    await client.aclose()


@pytest.mark.asyncio
async def test_malformed_entities_skipped():
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "success": True,
                "results": {
                    "entities": [
                        {"name": "Good", "entity_id": "1"},
                        {"name": "", "entity_id": "2"},
                        {"foo": "bar"},
                        "not-an-object",
                    ]
                },
            },
        )

    client = httpx.AsyncClient(
        transport=_transport(handler),
        base_url="https://hackathon.api.qloo.com",
    )
    async with QlooClient(_settings(), client=client) as qloo:
        entities, _ = await qloo.insights(
            filter_type="urn:entity:movie",
            entity_ids=["seed"],
            take=5,
        )
    assert [e.entity_id for e in entities] == ["1"]
    await client.aclose()


@pytest.mark.asyncio
async def test_missing_key_raises():
    settings = Settings(TASTEOS_MODE="demo", QLOO_API_KEY="")
    client = QlooClient(settings)
    with pytest.raises(QlooError, match="QLOO_API_KEY"):
        client._auth_headers()


@pytest.mark.asyncio
async def test_search_404_empty():
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"message": "No results"})

    client = httpx.AsyncClient(
        transport=_transport(handler),
        base_url="https://hackathon.api.qloo.com",
    )
    async with QlooClient(_settings(), client=client) as qloo:
        entities, meta = await qloo.search("zzzz-unknown", take=3)
    assert entities == []
    assert meta["status_code"] == 404
    await client.aclose()


@pytest.mark.asyncio
async def test_rate_limit_exhausted():
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"message": "slow down"})

    client = httpx.AsyncClient(
        transport=_transport(handler),
        base_url="https://hackathon.api.qloo.com",
    )
    async with QlooClient(_settings(QLOO_MAX_RETRIES=0), client=client) as qloo:
        with pytest.raises(QlooRateLimitError):
            await qloo.search("X", take=1)
    await client.aclose()


@pytest.mark.asyncio
async def test_affinity_not_fabricated_when_absent():
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "success": True,
                "results": {
                    "entities": [
                        {
                            "name": "No Affinity Place",
                            "entity_id": "CCC",
                            "subtype": "urn:entity:place",
                            "popularity": 0.5,
                        }
                    ]
                },
            },
        )

    client = httpx.AsyncClient(
        transport=_transport(handler),
        base_url="https://hackathon.api.qloo.com",
    )
    async with QlooClient(_settings(), client=client) as qloo:
        entities, _ = await qloo.insights(
            filter_type="urn:entity:place",
            entity_ids=["AAA"],
            location_query="New York",
            take=1,
        )
    assert entities[0].affinity_from_query() is None
    await client.aclose()
