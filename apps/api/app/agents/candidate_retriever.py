"""Cultural Candidate Retriever — calls Qloo or labeled demo dataset."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.agents.profile_resolver import ResolvedProfile
from app.core.config import Settings
from app.services.qloo.client import QlooClient, QlooError
from app.services.qloo.demo_data import DEMO_ENTITIES, DEMO_SOURCE, insights_demo
from app.services.qloo.entity_ids import is_qloo_entity_id, skipped_favorites_note
from app.services.qloo.models import QlooEntity

# Cache demo-* (and other named) resolutions for the process lifetime.
# Values are Qloo UUIDs, or None after a failed lookup (negative cache).
_DEMO_QLOO_ID_CACHE: dict[str, str | None] = {}


@dataclass
class RetrievedCandidate:
    entity: QlooEntity
    source: str  # qloo | tasteos_demo_dataset
    qloo_affinity: float | None
    meta: dict


@dataclass
class RetrieveResult:
    candidates: list[RetrievedCandidate]
    mode: str
    steps: list[dict] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)


class CulturalCandidateRetriever:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def retrieve(
        self,
        profiles: list[ResolvedProfile],
        *,
        target_domain: str,
        location_query: str | None,
        take: int,
    ) -> RetrieveResult:
        signal_ids: list[str] = []
        for profile in profiles:
            signal_ids.extend(profile.favorite_ids)
        # Deduplicate while preserving order
        seen: set[str] = set()
        unique_ids: list[str] = []
        for eid in signal_ids:
            if eid and eid not in seen:
                seen.add(eid)
                unique_ids.append(eid)

        if self.settings.is_live_mode:
            return await self._live(
                profiles, unique_ids, target_domain, location_query, take
            )
        return self._demo(unique_ids, target_domain, location_query, take)

    def _demo(
        self,
        entity_ids: list[str],
        target_domain: str,
        location_query: str | None,
        take: int,
    ) -> RetrieveResult:
        entities = insights_demo(
            filter_type=target_domain,
            entity_ids=entity_ids,
            location_query=location_query,
            take=take,
        )
        candidates = [
            RetrievedCandidate(
                entity=e,
                source=DEMO_SOURCE,
                qloo_affinity=None,  # never claim demo affinity as Qloo
                meta={"demo_seed_affinity": e.affinity_from_query()},
            )
            for e in entities
        ]
        return RetrieveResult(
            candidates=candidates,
            mode="demo",
            steps=[
                {
                    "stage": "candidate_retrieve",
                    "status": "ok",
                    "mode": "demo",
                    "source": DEMO_SOURCE,
                    "count": len(candidates),
                    "signal_entity_count": len(entity_ids),
                }
            ],
            limitations=[
                "Demo mode uses a curated sample dataset. Results are NOT from a live Qloo request.",
            ],
        )

    async def _live(
        self,
        profiles: list[ResolvedProfile],
        entity_ids: list[str],
        target_domain: str,
        location_query: str | None,
        take: int,
    ) -> RetrieveResult:
        limitations: list[str] = []

        async with QlooClient(self.settings) as client:
            live_ids, skipped = await self._resolve_live_signal_ids(
                profiles, entity_ids, client
            )
            note = skipped_favorites_note(skipped)
            if note:
                limitations.append(note)

            if not live_ids and not location_query:
                raise QlooError(
                    "Live mode needs real Qloo entity IDs (from /search) or a location_query."
                )

            entities, meta = await client.insights(
                filter_type=target_domain,
                entity_ids=live_ids or None,
                location_query=location_query,
                take=take,
                explainability=True,
            )

        candidates = [
            RetrievedCandidate(
                entity=e,
                source="qloo",
                qloo_affinity=e.affinity_from_query(),
                meta={"explainability": (e.query or {}).get("explainability")},
            )
            for e in entities
        ]
        base_limitations = [
            "Qloo affinity reflects cultural co-occurrence signals, not guaranteed "
            "personal preference or group consensus.",
        ]
        return RetrieveResult(
            candidates=candidates,
            mode="live",
            steps=[
                {
                    "stage": "candidate_retrieve",
                    "status": "ok",
                    "mode": "live",
                    "source": "qloo_insights",
                    "count": len(candidates),
                    "http_status": meta.get("status_code"),
                    "elapsed_ms": meta.get("elapsed_ms"),
                    "signal_entity_count": len(live_ids),
                    "skipped_favorite_count": skipped,
                }
            ],
            limitations=limitations + base_limitations,
        )

    async def _resolve_live_signal_ids(
        self,
        profiles: list[ResolvedProfile],
        entity_ids: list[str],
        client: QlooClient,
    ) -> tuple[list[str], int]:
        """Build UUID signal IDs for live Qloo; resolve demo-* favorites via search."""
        name_by_id = self._favorite_name_index(profiles)
        valid: list[str] = []
        seen: set[str] = set()
        skipped = 0

        for eid in entity_ids:
            if is_qloo_entity_id(eid):
                if eid not in seen:
                    seen.add(eid)
                    valid.append(eid)
                continue

            # Demo seed IDs are intentional placeholders — resolve to real Qloo UUIDs
            # so live plans reflect taste. Keep demo-* only for demo/mock mode.
            if eid.startswith("demo-"):
                resolved = await self._resolve_demo_favorite(client, eid, name_by_id)
                if resolved and resolved not in seen:
                    seen.add(resolved)
                    valid.append(resolved)
                else:
                    skipped += 1
                continue

            # local-*, unresolved-*, and any other non-UUID IDs are dropped.
            skipped += 1

        return valid, skipped

    @staticmethod
    def _favorite_name_index(
        profiles: list[ResolvedProfile],
    ) -> dict[str, tuple[str, str | None]]:
        index: dict[str, tuple[str, str | None]] = {}
        for eid, raw in DEMO_ENTITIES.items():
            index[eid] = (raw["name"], raw.get("subtype"))
        for profile in profiles:
            for fav in profile.favorites:
                eid = fav.get("entity_id")
                name = fav.get("name")
                if eid and name:
                    index[eid] = (name, fav.get("entity_type"))
        return index

    async def _resolve_demo_favorite(
        self,
        client: QlooClient,
        demo_id: str,
        name_by_id: dict[str, tuple[str, str | None]],
    ) -> str | None:
        if demo_id in _DEMO_QLOO_ID_CACHE:
            return _DEMO_QLOO_ID_CACHE[demo_id]

        name, entity_type = name_by_id.get(demo_id, (None, None))
        if not name and demo_id in DEMO_ENTITIES:
            raw = DEMO_ENTITIES[demo_id]
            name = raw["name"]
            entity_type = raw.get("subtype")
        if not name:
            _DEMO_QLOO_ID_CACHE[demo_id] = None
            return None

        types = [entity_type] if entity_type else None
        try:
            entities, _ = await client.search(name, types=types, take=5)
        except QlooError:
            _DEMO_QLOO_ID_CACHE[demo_id] = None
            return None

        chosen: str | None = None
        needle = name.strip().lower()
        for entity in entities:
            if not is_qloo_entity_id(entity.entity_id):
                continue
            if entity.name.strip().lower() == needle:
                chosen = entity.entity_id
                break
        if chosen is None:
            for entity in entities:
                if is_qloo_entity_id(entity.entity_id):
                    chosen = entity.entity_id
                    break

        _DEMO_QLOO_ID_CACHE[demo_id] = chosen
        return chosen


def clear_demo_qloo_id_cache() -> None:
    """Test helper — reset the process-local demo→Qloo ID cache."""
    _DEMO_QLOO_ID_CACHE.clear()
