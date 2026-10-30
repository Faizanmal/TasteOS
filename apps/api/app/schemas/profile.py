from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import EntityRef


class ProfileCreate(BaseModel):
    display_name: str = Field(min_length=1, max_length=120)
    favorites: list[EntityRef] = Field(default_factory=list, max_length=20)
    preferred_domains: list[str] = Field(default_factory=list, max_length=10)
    exclusions: list[str] = Field(default_factory=list, max_length=50)
    explicit_preferences: list[str] = Field(default_factory=list, max_length=20)
    notes: str | None = Field(default=None, max_length=1000)


class ProfileUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=120)
    favorites: list[EntityRef] | None = None
    preferred_domains: list[str] | None = None
    exclusions: list[str] | None = None
    explicit_preferences: list[str] | None = None
    notes: str | None = None


class ProfileOut(BaseModel):
    id: str
    display_name: str
    favorites: list[EntityRef]
    preferred_domains: list[str]
    exclusions: list[str]
    explicit_preferences: list[str]
    notes: str | None = None
    is_demo: bool = False
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
