"""Group Concierge orchestrator — resolve → retrieve → constrain → negotiate → compose → explain.

Does not re-implement the Qloo client; uses RecommendationService / agent modules.
"""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.explanation import BOOKING_DISCLAIMER, ExplanationGenerator
from app.agents.plan_composer import PlanComposer
from app.core.config import Settings
from app.models.recommendation import RecommendationRecord
from app.schemas.recommendation import (
    ConciergePlanRequest,
    ConciergePlanResponse,
    RecommendationRequest,
    RecommendationResponse,
)
from app.services.recommendations.service import RecommendationService


class ConciergeService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.recommendations = RecommendationService(settings)
        self.composer = PlanComposer()
        self.explainer = ExplanationGenerator()

    async def recommend(
        self,
        session: AsyncSession,
        payload: RecommendationRequest,
    ) -> RecommendationResponse:
        return await self.recommendations.recommend(session, payload)

    async def create_plan(
        self,
        session: AsyncSession,
        payload: ConciergePlanRequest,
    ) -> ConciergePlanResponse:
        # Retrieve enough candidates to satisfy primary + alternatives
        take = max(payload.take, payload.alternatives_count + 1)
        fetch_payload = payload.model_copy(update={"take": take})
        rec = await self.recommend(session, fetch_payload)
        if not rec.candidates:
            raise ValueError(
                "No candidates available to compose a plan after constraints. "
                "Try different profiles, location, or fewer exclusions."
            )

        primary = rec.candidates[0]
        alternatives = rec.candidates[1 : 1 + payload.alternatives_count]
        composed = self.composer.compose(
            experience=payload.experience,
            primary=primary,
            alternatives=alternatives,
            location_query=payload.location_query,
        )
        selection_rationale = self.explainer.selection_rationale(primary)
        tradeoffs = self.explainer.tradeoff_summary(primary, alternatives)
        limitations = list(rec.limitations)
        limitations.append(BOOKING_DISCLAIMER)
        limitations.append(self.explainer.evidence_vs_explanation_note())
        if payload.rejected_entity_ids:
            limitations.append(
                f"Regenerated excluding: {', '.join(payload.rejected_entity_ids)}."
            )

        plan_id = str(uuid.uuid4())
        response = ConciergePlanResponse(
            id=plan_id,
            mode=rec.mode,
            experience=payload.experience,
            primary=primary,
            alternatives=alternatives,
            itinerary=composed.itinerary,
            tradeoffs=tradeoffs,
            selection_rationale=selection_rationale,
            disclaimer=BOOKING_DISCLAIMER,
            reconciliation=primary.participant_matches,
            pipeline=[
                *rec.pipeline,
                *composed.steps,
                {
                    "stage": "explain",
                    "status": "ok",
                    "note": self.explainer.evidence_vs_explanation_note(),
                },
            ],
            limitations=limitations,
            rejected_entity_ids=list(payload.rejected_entity_ids),
        )
        record = RecommendationRecord(
            id=plan_id,
            kind="concierge_plan",
            mode=rec.mode,
            request_payload=payload.model_dump(),
            response_payload=response.model_dump(),
            rejected_entity_ids=list(payload.rejected_entity_ids),
        )
        session.add(record)
        await session.commit()
        return response

    async def reject_and_regenerate(
        self,
        session: AsyncSession,
        plan_id: str,
        entity_id: str,
    ) -> ConciergePlanResponse | None:
        """Load a prior plan, append entity_id to hard rejections, compose a new plan."""
        row = await session.get(RecommendationRecord, plan_id)
        if row is None:
            return None
        req = ConciergePlanRequest.model_validate(row.request_payload)
        rejected = list(
            dict.fromkeys(
                [*req.rejected_entity_ids, entity_id, *(row.rejected_entity_ids or [])]
            )
        )
        req.rejected_entity_ids = rejected
        return await self.create_plan(session, req)

    async def get_record(self, session: AsyncSession, record_id: str) -> dict | None:
        return await self.recommendations.get(session, record_id)
