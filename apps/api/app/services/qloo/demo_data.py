"""Curated demo dataset — clearly labeled, never presented as live Qloo results."""

from __future__ import annotations

from copy import deepcopy

from app.services.qloo.models import QlooEntity

DEMO_SOURCE = "tasteos_demo_dataset"

# Stable demo entity IDs (not real Qloo UUIDs).
DEMO_ENTITIES: dict[str, dict] = {
    "demo-artist-radiohead": {
        "name": "Radiohead",
        "entity_id": "demo-artist-radiohead",
        "type": "urn:entity",
        "subtype": "urn:entity:artist",
        "properties": {
            "description": "English rock band known for experimental and alternative work.",
            "image": {"url": None},
        },
        "tags": [{"name": "Alternative Rock", "type": "urn:tag:genre"}],
    },
    "demo-artist-beyonce": {
        "name": "Beyoncé",
        "entity_id": "demo-artist-beyonce",
        "type": "urn:entity",
        "subtype": "urn:entity:artist",
        "properties": {
            "description": "American singer, songwriter, and performer.",
        },
        "tags": [{"name": "R&B", "type": "urn:tag:genre"}],
    },
    "demo-movie-parasite": {
        "name": "Parasite",
        "entity_id": "demo-movie-parasite",
        "type": "urn:entity",
        "subtype": "urn:entity:movie",
        "properties": {
            "description": "A Korean dark comedy thriller about class and family.",
            "release_year": 2019,
        },
        "tags": [{"name": "Thriller", "type": "urn:tag:genre"}],
    },
    "demo-movie-everything": {
        "name": "Everything Everywhere All at Once",
        "entity_id": "demo-movie-everything",
        "type": "urn:entity",
        "subtype": "urn:entity:movie",
        "properties": {
            "description": "A multiverse adventure about family and possibility.",
            "release_year": 2022,
        },
        "tags": [{"name": "Sci-Fi", "type": "urn:tag:genre"}],
    },
    "demo-brand-patagonia": {
        "name": "Patagonia",
        "entity_id": "demo-brand-patagonia",
        "type": "urn:entity",
        "subtype": "urn:entity:brand",
        "properties": {
            "description": "Outdoor apparel brand associated with sustainability."
        },
        "tags": [{"name": "Outdoor", "type": "urn:tag:genre"}],
    },
    "demo-tv-the-bear": {
        "name": "The Bear",
        "entity_id": "demo-tv-the-bear",
        "type": "urn:entity",
        "subtype": "urn:entity:tv_show",
        "properties": {
            "description": "A chef returns home to run a chaotic neighborhood restaurant."
        },
        "tags": [{"name": "Drama", "type": "urn:tag:genre"}],
    },
    "demo-place-balthazar": {
        "name": "Balthazar",
        "entity_id": "demo-place-balthazar",
        "type": "urn:entity",
        "subtype": "urn:entity:place",
        "properties": {
            "description": "Classic French brasserie atmosphere in Manhattan.",
            "address": "New York, NY",
        },
        "tags": [{"name": "French", "type": "urn:tag:cuisine"}],
        "query": {"affinity": 0.82},
    },
    "demo-place-momofuku": {
        "name": "Momofuku Noodle Bar",
        "entity_id": "demo-place-momofuku",
        "type": "urn:entity",
        "subtype": "urn:entity:place",
        "properties": {
            "description": "Inventive noodles and shared plates with a lively energy.",
            "address": "New York, NY",
        },
        "tags": [{"name": "Asian Fusion", "type": "urn:tag:cuisine"}],
        "query": {"affinity": 0.78},
    },
    "demo-place-via-carota": {
        "name": "Via Carota",
        "entity_id": "demo-place-via-carota",
        "type": "urn:entity",
        "subtype": "urn:entity:place",
        "properties": {
            "description": "Warm Italian trattoria known for seasonal plates.",
            "address": "New York, NY",
        },
        "tags": [{"name": "Italian", "type": "urn:tag:cuisine"}],
        "query": {"affinity": 0.74},
    },
    "demo-place-eleven-madison": {
        "name": "Eleven Madison Park",
        "entity_id": "demo-place-eleven-madison",
        "type": "urn:entity",
        "subtype": "urn:entity:place",
        "properties": {
            "description": "Elevated plant-forward fine dining experience.",
            "address": "New York, NY",
        },
        "tags": [{"name": "Fine Dining", "type": "urn:tag:cuisine"}],
        "query": {"affinity": 0.61},
    },
    "demo-place-russ-daughters": {
        "name": "Russ & Daughters Cafe",
        "entity_id": "demo-place-russ-daughters",
        "type": "urn:entity",
        "subtype": "urn:entity:place",
        "properties": {
            "description": "Iconic appetizing counter culture — smoked fish and cafe plates.",
            "address": "New York, NY",
        },
        "tags": [{"name": "Cafe", "type": "urn:tag:cuisine"}],
        "query": {"affinity": 0.69},
    },
    "demo-place-katzs": {
        "name": "Katz's Delicatessen",
        "entity_id": "demo-place-katzs",
        "type": "urn:entity",
        "subtype": "urn:entity:place",
        "properties": {
            "description": "Historic Jewish delicatessen known for pastrami sandwiches.",
            "address": "New York, NY",
        },
        "tags": [{"name": "Deli", "type": "urn:tag:cuisine"}],
        "query": {"affinity": 0.66},
    },
}

DEMO_PROFILES = [
    {
        "id": "demo-profile-maya",
        "display_name": "Maya",
        "preferred_domains": ["urn:entity:movie", "urn:entity:place"],
        "favorites": [
            {
                "entity_id": "demo-movie-parasite",
                "name": "Parasite",
                "entity_type": "urn:entity:movie",
            },
            {
                "entity_id": "demo-artist-radiohead",
                "name": "Radiohead",
                "entity_type": "urn:entity:artist",
            },
            {
                "entity_id": "demo-tv-the-bear",
                "name": "The Bear",
                "entity_type": "urn:entity:tv_show",
            },
        ],
        "exclusions": ["demo-place-eleven-madison"],
        "explicit_preferences": ["adventurous dining", "indie culture"],
    },
    {
        "id": "demo-profile-jordan",
        "display_name": "Jordan",
        "preferred_domains": ["urn:entity:artist", "urn:entity:place"],
        "favorites": [
            {
                "entity_id": "demo-artist-beyonce",
                "name": "Beyoncé",
                "entity_type": "urn:entity:artist",
            },
            {
                "entity_id": "demo-movie-everything",
                "name": "Everything Everywhere All at Once",
                "entity_type": "urn:entity:movie",
            },
            {
                "entity_id": "demo-brand-patagonia",
                "name": "Patagonia",
                "entity_type": "urn:entity:brand",
            },
        ],
        "exclusions": [],
        "explicit_preferences": ["lively atmosphere", "shareable plates"],
    },
    {
        "id": "demo-profile-sam",
        "display_name": "Sam",
        "preferred_domains": ["urn:entity:place", "urn:entity:brand"],
        "favorites": [
            {
                "entity_id": "demo-tv-the-bear",
                "name": "The Bear",
                "entity_type": "urn:entity:tv_show",
            },
            {
                "entity_id": "demo-brand-patagonia",
                "name": "Patagonia",
                "entity_type": "urn:entity:brand",
            },
            {
                "entity_id": "demo-artist-radiohead",
                "name": "Radiohead",
                "entity_type": "urn:entity:artist",
            },
        ],
        "exclusions": ["demo-place-katzs"],
        "explicit_preferences": ["walkable neighborhood", "comfort food"],
    },
]


def entity_as_model(entity_id: str) -> QlooEntity:
    raw = DEMO_ENTITIES[entity_id]
    return QlooEntity.model_validate(deepcopy(raw))


def search_demo(
    query: str, types: list[str] | None = None, take: int = 10
) -> list[QlooEntity]:
    q = query.strip().lower()
    results: list[QlooEntity] = []
    for item in DEMO_ENTITIES.values():
        if (
            types
            and item.get("subtype")
            and item["subtype"] not in types
            and item["subtype"].replace("urn:entity:", "") not in types
        ):
            # Also allow short type forms
            short = item["subtype"].split(":")[-1]
            type_ok = any(t.endswith(short) or t == item["subtype"] for t in types)
            if not type_ok:
                continue
        hay = f"{item['name']} {item.get('properties', {}).get('description', '')}".lower()
        if q in hay or not q:
            results.append(QlooEntity.model_validate(deepcopy(item)))
    return results[:take]


def insights_demo(
    *,
    filter_type: str,
    entity_ids: list[str] | None = None,
    location_query: str | None = None,
    take: int = 10,
) -> list[QlooEntity]:
    """Return place (or other) candidates with synthetic affinities labeled as demo."""
    _ = location_query, entity_ids
    candidates = [
        entity_as_model(eid)
        for eid, raw in DEMO_ENTITIES.items()
        if raw.get("subtype") == filter_type
    ]
    # Deterministic ordering by pre-seeded affinity then name.
    candidates.sort(
        key=lambda e: (-(e.affinity_from_query() or 0.0), e.name.lower()),
    )
    return candidates[:take]
