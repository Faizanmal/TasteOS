"""Profile persistence repository (SQLAlchemy)."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.profile import TasteProfile


class ProfileRepository:
    async def create(self, session: AsyncSession, **fields) -> TasteProfile:
        row = TasteProfile(**fields)
        session.add(row)
        await session.commit()
        await session.refresh(row)
        return row

    async def get(self, session: AsyncSession, profile_id: str) -> TasteProfile | None:
        return await session.get(TasteProfile, profile_id)

    async def update(
        self, session: AsyncSession, row: TasteProfile, **fields
    ) -> TasteProfile:
        for key, value in fields.items():
            setattr(row, key, value)
        row.updated_at = datetime.now(UTC)
        await session.commit()
        await session.refresh(row)
        return row

    async def delete(self, session: AsyncSession, row: TasteProfile) -> None:
        await session.delete(row)
        await session.commit()

    async def list_recent(
        self, session: AsyncSession, limit: int = 20
    ) -> list[TasteProfile]:
        result = await session.execute(
            select(TasteProfile).order_by(TasteProfile.created_at.desc()).limit(limit)
        )
        return list(result.scalars().all())
