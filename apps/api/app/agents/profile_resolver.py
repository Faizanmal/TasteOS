"""Taste Profile Resolver — loads and normalizes participant preferences."""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.profile import TasteProfile
from app.services.qloo.demo_data import DEMO_PROFILES


@dataclass
class ResolvedProfile:
    id: str
    display_name: str
    favorite_ids: list[str]
    favorites: list[dict]
    preferred_domains: list[str]
    exclusions: set[str]
    explicit_preferences: list[str]
    is_demo: bool = False


@dataclass
class ResolveResult:
    profiles: list[ResolvedProfile]
    steps: list[dict] = field(default_factory=list)


class TasteProfileResolver:
    async def resolve(
        self,
        session: AsyncSession,
        profile_ids: list[str],
    ) -> ResolveResult:
        steps: list[dict] = []
        resolved: list[ResolvedProfile] = []
        demo_by_id = {p["id"]: p for p in DEMO_PROFILES}

        for pid in profile_ids:
            if pid in demo_by_id:
                demo = demo_by_id[pid]
                resolved.append(
                    ResolvedProfile(
                        id=demo["id"],
                        display_name=demo["display_name"],
                        favorite_ids=[f["entity_id"] for f in demo["favorites"]],
                        favorites=list(demo["favorites"]),
                        preferred_domains=list(demo["preferred_domains"]),
                        exclusions=set(demo.get("exclusions") or []),
                        explicit_preferences=list(
                            demo.get("explicit_preferences") or []
                        ),
                        is_demo=True,
                    )
                )
                continue

            result = await session.execute(
                select(TasteProfile).where(TasteProfile.id == pid)
            )
            row = result.scalar_one_or_none()
            if row is None:
                raise ValueError(f"Profile not found: {pid}")
            favorites = row.favorites or []
            resolved.append(
                ResolvedProfile(
                    id=row.id,
                    display_name=row.display_name,
                    favorite_ids=[
                        f.get("entity_id") for f in favorites if f.get("entity_id")
                    ],
                    favorites=list(favorites),
                    preferred_domains=list(row.preferred_domains or []),
                    exclusions=set(row.exclusions or []),
                    explicit_preferences=list(row.explicit_preferences or []),
                    is_demo=bool(row.is_demo),
                )
            )

        steps.append(
            {
                "stage": "profile_resolve",
                "status": "ok",
                "participant_count": len(resolved),
                "profile_ids": [p.id for p in resolved],
            }
        )
        return ResolveResult(profiles=resolved, steps=steps)
