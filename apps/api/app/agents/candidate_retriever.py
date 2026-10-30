"""Cultural Candidate Retriever — calls Qloo or labeled demo dataset."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.agents.profile_resolver import ResolvedProfile
from app.core.config import Settings
from app.services.qloo.client import QlooClient, QlooError
from app.services.qloo.demo_data import DEMO_SOURCE, insights_demo
from app.services.qloo.models import QlooEntity


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
            return await self._live(unique_ids, target_domain, location_query, take)
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
        entity_ids: list[str],
        target_domain: str,
        location_query: str | None,
        take: int,
    ) -> RetrieveResult:
        limitations: list[str] = []
        # Filter out demo entity IDs — they are not valid Qloo UUIDs
        live_ids = [eid for eid in entity_ids if not eid.startswith("demo-")]
        if len(live_ids) < len(entity_ids):
            limitations.append(
                "Some profile favorites use demo entity IDs and were omitted from the Qloo signal."
            )
        if not live_ids and not location_query:
            raise QlooError(
                "Live mode needs real Qloo entity IDs (from /search) or a location_query."
            )

        async with QlooClient(self.settings) as client:
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
                }
            ],
            limitations=limitations
            or [
                "Qloo affinity reflects cultural co-occurrence signals, not guaranteed personal preference or group consensus.",
            ],
        )
