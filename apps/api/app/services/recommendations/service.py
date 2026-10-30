"""TasteOS Core recommendation service.

Live mode calls the verified Qloo client. Demo mode uses the labeled sample dataset.
Application ranking (`app_rank_score`) is never presented as a Qloo score.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.candidate_retriever import CulturalCandidateRetriever
from app.agents.constraint_evaluator import ConstraintEvaluator
from app.agents.negotiation import NegotiationEngine
from app.agents.profile_resolver import TasteProfileResolver
from app.core.config import Settings
from app.models.recommendation import RecommendationRecord
from app.schemas.recommendation import (
    CandidateOut,
    RecommendationRequest,
    RecommendationResponse,
)
from app.services.qloo.client import INSIGHTS_ENTITY_TYPES, QlooError


class RecommendationService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.resolver = TasteProfileResolver()
        self.retriever = CulturalCandidateRetriever(settings)
        self.constraints = ConstraintEvaluator()
        self.negotiation = NegotiationEngine()

    def _validate_request(self, payload: RecommendationRequest) -> None:
        if payload.target_domain not in INSIGHTS_ENTITY_TYPES:
            raise ValueError(
                f"Unsupported target_domain '{payload.target_domain}'. "
                f"Allowed: {sorted(INSIGHTS_ENTITY_TYPES)}"
            )
        if self.settings.is_live_mode and not self.settings.qloo_configured:
            raise QlooError(
                "TASTEOS_MODE=live requires QLOO_API_KEY for recommendations.",
                status_code=503,
            )

    @staticmethod
    def _apply_provenance(
        candidates: list[CandidateOut], mode: str
    ) -> list[CandidateOut]:
        cleaned: list[CandidateOut] = []
        for cand in candidates:
            dumped = cand.model_dump()
            if mode == "demo":
                dumped["qloo_affinity"] = None
                if dumped.get("source") == "qloo":
                    dumped["source"] = "tasteos_demo_dataset"
                for match in dumped.get("participant_matches") or []:
                    match["qloo_affinity"] = None
            cleaned.append(CandidateOut.model_validate(dumped))
        return cleaned

    async def recommend(
        self,
        session: AsyncSession,
        payload: RecommendationRequest,
        *,
        persist: bool = True,
    ) -> RecommendationResponse:
        self._validate_request(payload)
        mode = self.settings.tasteos_mode

        resolved = await self.resolver.resolve(session, payload.profile_ids)
        retrieved = await self.retriever.retrieve(
            resolved.profiles,
            target_domain=payload.target_domain,
            location_query=payload.location_query,
            take=max(payload.take, 8),
        )
        constrained = self.constraints.evaluate(
            retrieved.candidates,
            resolved.profiles,
            exclusions=payload.exclusions,
            rejected_entity_ids=payload.rejected_entity_ids,
            budget=payload.budget,
        )
        negotiated = self.negotiation.rank(
            constrained.kept,
            resolved.profiles,
            mode=retrieved.mode,
        )
        pipeline = [
            *resolved.steps,
            *retrieved.steps,
            *constrained.steps,
            *negotiated.steps,
            {
                "stage": "provenance",
                "status": "ok",
                "note": (
                    "qloo_affinity is copied from Qloo entity.query when present; "
                    "app_rank_score is TasteOS negotiation logic (tasteos_negotiation_v1)."
                ),
            },
        ]
        limitations = list(retrieved.limitations)
        if not negotiated.ranked:
            limitations.append("No candidates remained after constraints.")

        cleaned = self._apply_provenance(negotiated.ranked[: payload.take], mode)
        record_id = str(uuid.uuid4())
        response = RecommendationResponse(
            id=record_id,
            mode=mode,  # type: ignore[arg-type]
            target_domain=payload.target_domain,
            location_query=payload.location_query,
            candidates=cleaned,
            pipeline=pipeline,
            limitations=limitations,
            created_at=datetime.now(UTC).isoformat(),
        )

        if persist:
            record = RecommendationRecord(
                id=record_id,
                kind="recommendation",
                mode=mode,
                request_payload=payload.model_dump(),
                response_payload=response.model_dump(),
                rejected_entity_ids=list(payload.rejected_entity_ids),
            )
            session.add(record)
            await session.commit()
        return response

    async def get(self, session: AsyncSession, recommendation_id: str) -> dict | None:
        row = await session.get(RecommendationRecord, recommendation_id)
        if row is None:
            return None
        return row.response_payload
