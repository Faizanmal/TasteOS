"""FastAPI dependencies."""

from __future__ import annotations

from fastapi import Header, HTTPException, status

from app.core.config import get_settings


async def optional_api_key(
    x_tasteos_key: str | None = Header(default=None, alias="X-TasteOS-Key"),
) -> None:
    settings = get_settings()
    if not settings.tasteos_api_key:
        return
    if x_tasteos_key != settings.tasteos_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing X-TasteOS-Key",
        )
