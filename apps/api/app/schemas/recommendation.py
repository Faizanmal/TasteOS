from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import ModeLiteral, SourceLiteral
from app.services.qloo.client import INSIGHTS_ENTITY_TYPES


class RecommendationRequest(BaseModel):
    profile_ids: list[str] = Field(min_length=1, max_length=8)
    target_domain: str = Field(default="urn:entity:place")
    location_query: str | None = Field(default="New York", max_length=200)
    budget: Literal["any", "casual", "mid", "upscale"] | None = "any"
    exclusions: list[str] = Field(default_factory=list, max_length=50)
    take: int = Field(default=8, ge=1, le=20)
    rejected_entity_ids: list[str] = Field(default_factory=list, max_length=50)

    @field_validator("target_domain")
    @classmethod
    def validate_domain(cls, value: str) -> str:
        cleaned = value.strip()
        if cleaned not in INSIGHTS_ENTITY_TYPES:
            raise ValueError(
                f"Unsupported target_domain '{cleaned}'. Allowed: {sorted(INSIGHTS_ENTITY_TYPES)}"
            )
        return cleaned

    @field_validator("profile_ids")
    @classmethod
    def nonempty_ids(cls, value: list[str]) -> list[str]:
        cleaned = [v.strip() for v in value if v and v.strip()]
        if not cleaned:
            raise ValueError("profile_ids must contain at least one id")
        return cleaned


class ParticipantMatch(BaseModel):
    profile_id: str
    display_name: str
    status: Literal["supported", "unknown", "conflict", "excluded"]
    evidence: list[str] = Field(default_factory=list)
    app_score: float | None = None
    qloo_affinity: float | None = None
    notes: str


class CandidateOut(BaseModel):
    entity_id: str
    name: str
    category: str
    description: str | None = None
    image_url: str | None = None
    source: SourceLiteral
    qloo_affinity: float | None = None
    app_rank_score: float
    participant_matches: list[ParticipantMatch]
    evidence_refs: list[str] = Field(default_factory=list)
    match_explanation: str
    limitations: list[str] = Field(default_factory=list)
    ranking_inputs: dict[str, Any] = Field(default_factory=dict)


class RecommendationResponse(BaseModel):
    id: str
    mode: ModeLiteral
    target_domain: str
    location_query: str | None
    candidates: list[CandidateOut]
    pipeline: list[dict[str, Any]]
    limitations: list[str]
    created_at: str


class ConciergePlanRequest(RecommendationRequest):
    experience: Literal["evening_out", "dinner", "drinks", "culture_night"] = (
        "evening_out"
    )
    alternatives_count: int = Field(
        default=3,
        ge=0,
        le=10,
        description="How many ranked alternatives to return alongside the primary pick",
    )


class PlanStop(BaseModel):
    order: int
    kind: Literal["dinner", "drinks", "walk", "show"]
    candidate: CandidateOut | None = None
    title: str
    detail: str
    is_proposed: bool = True


class ConciergePlanResponse(BaseModel):
    id: str
    mode: ModeLiteral
    experience: str
    primary: CandidateOut
    alternatives: list[CandidateOut]
    itinerary: list[PlanStop]
    tradeoffs: str
    selection_rationale: str
    disclaimer: str
    reconciliation: list[ParticipantMatch]
    pipeline: list[dict[str, Any]]
    limitations: list[str]
    rejected_entity_ids: list[str] = Field(default_factory=list)
