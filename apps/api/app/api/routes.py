"""TasteOS HTTP API routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app import __version__
from app.api.deps import optional_api_key
from app.core.config import Settings, get_settings
from app.core.database import get_db, ping_db
from app.schemas.common import HealthResponse, ModeInfo
from app.schemas.profile import ProfileCreate, ProfileOut, ProfileUpdate
from app.schemas.recommendation import (
    ConciergePlanRequest,
    ConciergePlanResponse,
    RecommendationRequest,
    RecommendationResponse,
)
from app.services.concierge.service import ConciergeService
from app.services.profiles.service import ProfileService
from app.services.qloo.client import QlooClient
from app.services.qloo.demo_data import DEMO_SOURCE, search_demo
from app.services.recommendations.service import RecommendationService

router = APIRouter()
profiles = ProfileService()


def _mode_info(settings: Settings) -> ModeInfo:
    if settings.is_live_mode:
        return ModeInfo(
            mode="live",
            qloo_key_configured=settings.qloo_configured,
            label="Live mode",
            description="Requests call the Qloo hackathon API. Responses include retrieved Qloo entities.",
        )
    return ModeInfo(
        mode="demo",
        qloo_key_configured=settings.qloo_configured,
        label="Demo mode",
        description=(
            f"Uses the labeled `{DEMO_SOURCE}` sample dataset. "
            "Results are NOT from a live Qloo request."
        ),
    )


@router.get("/health", response_model=HealthResponse, tags=["system"])
async def health(settings: Settings = Depends(get_settings)) -> HealthResponse:
    db_ok = await ping_db()
    return HealthResponse(
        status="ok" if db_ok else "degraded",
        mode=settings.tasteos_mode,  # type: ignore[arg-type]
        qloo_key_configured=settings.qloo_configured,
        version=__version__,
        details={
            "frontend_url": settings.frontend_url,
            "database": "ok" if db_ok else "unavailable",
        },
    )


@router.get("/api/v1/mode", response_model=ModeInfo, tags=["system"])
async def get_mode(settings: Settings = Depends(get_settings)) -> ModeInfo:
    return _mode_info(settings)


@router.get("/api/v1/search", tags=["qloo"])
async def search_entities(
    query: str = Query(min_length=1, max_length=200),
    types: str | None = Query(default=None, description="Comma-separated entity types"),
    take: int = Query(default=8, ge=1, le=30),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    type_list = [t.strip() for t in types.split(",") if t.strip()] if types else None
    if settings.is_live_mode:
        async with QlooClient(settings) as client:
            entities, meta = await client.search(query, types=type_list, take=take)
        return {
            "mode": "live",
            "source": "qloo",
            "meta": meta,
            "results": [e.model_dump() for e in entities],
        }

    entities = search_demo(query, types=type_list, take=take)
    return {
        "mode": "demo",
        "source": DEMO_SOURCE,
        "meta": {
            "note": "Demo search results are curated samples, not live Qloo data."
        },
        "results": [e.model_dump() for e in entities],
    }


@router.get("/api/v1/profiles/demo", response_model=list[ProfileOut], tags=["profiles"])
async def list_demo_profiles() -> list[ProfileOut]:
    return await profiles.list_demo()


@router.post(
    "/api/v1/profiles",
    response_model=ProfileOut,
    status_code=status.HTTP_201_CREATED,
    tags=["profiles"],
    dependencies=[Depends(optional_api_key)],
    summary="Create an anonymous taste profile",
)
async def create_profile(
    payload: ProfileCreate,
    session: AsyncSession = Depends(get_db),
) -> ProfileOut:
    return await profiles.create(session, payload)


@router.get(
    "/api/v1/profiles/{profile_id}",
    response_model=ProfileOut,
    tags=["profiles"],
    summary="Get a taste profile by id",
)
async def get_profile(
    profile_id: str,
    session: AsyncSession = Depends(get_db),
) -> ProfileOut:
    row = await profiles.get(session, profile_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    return row


@router.patch(
    "/api/v1/profiles/{profile_id}",
    response_model=ProfileOut,
    tags=["profiles"],
    dependencies=[Depends(optional_api_key)],
    summary="Update a taste profile",
)
async def update_profile(
    profile_id: str,
    payload: ProfileUpdate,
    session: AsyncSession = Depends(get_db),
) -> ProfileOut:
    row = await profiles.update(session, profile_id, payload)
    if row is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    return row


@router.post(
    "/api/v1/profiles/{profile_id}/reset",
    response_model=ProfileOut,
    tags=["profiles"],
    dependencies=[Depends(optional_api_key)],
    summary="Reset favorites/exclusions on a profile (keeps id)",
)
async def reset_profile(
    profile_id: str,
    session: AsyncSession = Depends(get_db),
) -> ProfileOut:
    row = await profiles.reset(session, profile_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    return row


@router.delete(
    "/api/v1/profiles/{profile_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["profiles"],
    dependencies=[Depends(optional_api_key)],
    summary="Delete a taste profile",
)
async def delete_profile(
    profile_id: str,
    session: AsyncSession = Depends(get_db),
) -> None:
    ok = await profiles.delete(session, profile_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Profile not found")


@router.post(
    "/api/v1/recommendations",
    response_model=RecommendationResponse,
    tags=["recommendations"],
    summary="Generate recommendations for one or more profiles",
)
async def create_recommendation(
    payload: RecommendationRequest,
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> RecommendationResponse:
    service = RecommendationService(settings)
    return await service.recommend(session, payload)


@router.get(
    "/api/v1/recommendations/{recommendation_id}",
    tags=["recommendations"],
    summary="Retrieve a persisted recommendation payload",
)
async def get_recommendation(
    recommendation_id: str,
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    service = RecommendationService(settings)
    data = await service.get(session, recommendation_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Recommendation not found")
    return data


@router.post(
    "/api/v1/concierge/plan",
    response_model=ConciergePlanResponse,
    tags=["concierge"],
    summary="Propose a shared outing (Group Concierge)",
    description=(
        "Runs resolve → retrieve → constrain → negotiate → compose → explain. "
        "Returns a **proposed** itinerary only — never confirms bookings. "
        "`app_rank_score` is TasteOS negotiation; `qloo_affinity` is retrieved evidence when present."
    ),
)
async def create_concierge_plan(
    payload: ConciergePlanRequest,
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> ConciergePlanResponse:
    service = ConciergeService(settings)
    return await service.create_plan(session, payload)


@router.post(
    "/api/v1/concierge/plan/{plan_id}/reject",
    response_model=ConciergePlanResponse,
    tags=["concierge"],
    summary="Reject a candidate and regenerate the plan",
    description="Appends entity_id to hard rejections and recomputes a new proposed plan.",
)
async def reject_and_regenerate(
    plan_id: str,
    entity_id: str = Query(..., min_length=1, description="Entity id to reject"),
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> ConciergePlanResponse:
    service = ConciergeService(settings)
    plan = await service.reject_and_regenerate(session, plan_id, entity_id.strip())
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan not found")
    return plan


@router.get(
    "/api/v1/concierge/plan/{plan_id}",
    tags=["concierge"],
    summary="Retrieve a persisted concierge plan",
)
async def get_concierge_plan(
    plan_id: str,
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    service = ConciergeService(settings)
    data = await service.get_record(session, plan_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Plan not found")
    return data
