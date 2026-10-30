"""Taste profile CRUD — anonymous nicknames only; no unnecessary PII."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.profiles import ProfileRepository
from app.schemas.common import EntityRef
from app.schemas.profile import ProfileCreate, ProfileOut, ProfileUpdate
from app.services.qloo.client import INSIGHTS_ENTITY_TYPES
from app.services.qloo.demo_data import DEMO_PROFILES

_DEMO_TS = datetime(2026, 1, 1, tzinfo=UTC)


def _demo_out(demo: dict) -> ProfileOut:
    return ProfileOut(
        id=demo["id"],
        display_name=demo["display_name"],
        favorites=[EntityRef.model_validate(f) for f in demo["favorites"]],
        preferred_domains=list(demo.get("preferred_domains") or []),
        exclusions=list(demo.get("exclusions") or []),
        explicit_preferences=list(demo.get("explicit_preferences") or []),
        notes=None,
        is_demo=True,
        created_at=_DEMO_TS,
        updated_at=_DEMO_TS,
    )


def _validate_domains(domains: list[str]) -> None:
    bad = [d for d in domains if d not in INSIGHTS_ENTITY_TYPES]
    if bad:
        raise ValueError(
            f"Unsupported preferred_domains: {bad}. Allowed: {sorted(INSIGHTS_ENTITY_TYPES)}"
        )


class ProfileService:
    def __init__(self) -> None:
        self.repo = ProfileRepository()

    async def create(self, session: AsyncSession, payload: ProfileCreate) -> ProfileOut:
        _validate_domains(payload.preferred_domains)
        row = await self.repo.create(
            session,
            display_name=payload.display_name.strip(),
            favorites=[f.model_dump() for f in payload.favorites],
            preferred_domains=payload.preferred_domains,
            exclusions=payload.exclusions,
            explicit_preferences=payload.explicit_preferences,
            notes=payload.notes,
            is_demo=False,
        )
        return ProfileOut.model_validate(row)

    async def get(self, session: AsyncSession, profile_id: str) -> ProfileOut | None:
        for demo in DEMO_PROFILES:
            if demo["id"] == profile_id:
                return _demo_out(demo)
        row = await self.repo.get(session, profile_id)
        if row is None:
            return None
        return ProfileOut.model_validate(row)

    async def list_demo(self) -> list[ProfileOut]:
        return [_demo_out(demo) for demo in DEMO_PROFILES]

    async def update(
        self,
        session: AsyncSession,
        profile_id: str,
        payload: ProfileUpdate,
    ) -> ProfileOut | None:
        if profile_id.startswith("demo-"):
            raise PermissionError(
                "Demo profiles are read-only. Create a new anonymous profile to edit."
            )
        row = await self.repo.get(session, profile_id)
        if row is None:
            return None
        data = payload.model_dump(exclude_unset=True)
        if "preferred_domains" in data and data["preferred_domains"] is not None:
            _validate_domains(data["preferred_domains"])
        if "favorites" in data and payload.favorites is not None:
            data["favorites"] = [f.model_dump() for f in payload.favorites]
        if "display_name" in data and isinstance(data["display_name"], str):
            data["display_name"] = data["display_name"].strip()
        row = await self.repo.update(session, row, **data)
        return ProfileOut.model_validate(row)

    async def reset(self, session: AsyncSession, profile_id: str) -> ProfileOut | None:
        """Clear favorites/exclusions/preferences while keeping the anonymous profile id."""
        if profile_id.startswith("demo-"):
            raise PermissionError("Demo profiles cannot be reset.")
        row = await self.repo.get(session, profile_id)
        if row is None:
            return None
        row = await self.repo.update(
            session,
            row,
            favorites=[],
            exclusions=[],
            explicit_preferences=[],
            preferred_domains=[],
            notes=None,
        )
        return ProfileOut.model_validate(row)

    async def delete(self, session: AsyncSession, profile_id: str) -> bool:
        if profile_id.startswith("demo-"):
            raise PermissionError("Demo profiles cannot be deleted.")
        row = await self.repo.get(session, profile_id)
        if row is None:
            return False
        await self.repo.delete(session, row)
        return True
