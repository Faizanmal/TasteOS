from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

ModeLiteral = Literal["demo", "live"]
SourceLiteral = Literal["qloo", "tasteos_demo_dataset", "application_logic"]


class EntityRef(BaseModel):
    """Favorite cultural entity reference. Prefer Qloo entity_ids from /search in live mode."""

    entity_id: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=200)
    entity_type: str = Field(min_length=1, max_length=80)
    image_url: str | None = Field(default=None, max_length=500)
    description: str | None = Field(default=None, max_length=2000)

    @field_validator("entity_id", "name", "entity_type")
    @classmethod
    def strip_nonempty(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("must be a non-empty string")
        return cleaned


class ModeInfo(BaseModel):
    mode: ModeLiteral
    qloo_key_configured: bool
    label: str
    description: str


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    mode: ModeLiteral
    qloo_key_configured: bool
    version: str
    details: dict[str, Any] = Field(default_factory=dict)
