"""Plan Composer — assembles a proposed itinerary (not a booking)."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.agents.explanation import BOOKING_DISCLAIMER
from app.schemas.recommendation import CandidateOut, PlanStop


@dataclass
class PlanComposeResult:
    itinerary: list[PlanStop]
    tradeoffs: str
    steps: list[dict] = field(default_factory=list)


class PlanComposer:
    def compose(
        self,
        *,
        experience: str,
        primary: CandidateOut,
        alternatives: list[CandidateOut],
        location_query: str | None,
    ) -> PlanComposeResult:
        place = location_query or "the city"
        primary_kind = "dinner" if experience in {"evening_out", "dinner"} else "drinks"
        if experience == "culture_night":
            primary_kind = "show"

        itinerary = [
            PlanStop(
                order=1,
                kind="walk",
                candidate=None,
                title=f"Meet near {place}",
                detail=(f"Proposed meetup window near {place}. {BOOKING_DISCLAIMER}"),
                is_proposed=True,
            ),
            PlanStop(
                order=2,
                kind=primary_kind,  # type: ignore[arg-type]
                candidate=primary,
                title=f"Primary stop: {primary.name}",
                detail=(
                    f"TasteOS proposes {primary.name} ({primary.category}) as the shared anchor. "
                    f"{BOOKING_DISCLAIMER}"
                ),
                is_proposed=True,
            ),
        ]
        if experience in {"evening_out", "culture_night", "drinks"} and alternatives:
            backup = alternatives[0]
            itinerary.append(
                PlanStop(
                    order=3,
                    kind="walk",
                    candidate=backup,
                    title=f"Backup option: {backup.name}",
                    detail=(
                        "Keep a ranked alternative ready if the group rejects the primary pick. "
                        f"{BOOKING_DISCLAIMER}"
                    ),
                    is_proposed=True,
                )
            )

        tradeoffs = (
            f"Primary pick balances fairness and coverage across participants. "
            f"Alternatives ranked next: {', '.join(a.name for a in alternatives[:3]) or 'none'}. "
            f"{BOOKING_DISCLAIMER}"
        )
        steps = [
            {
                "stage": "plan_compose",
                "status": "ok",
                "stops": len(itinerary),
                "proposed_only": True,
            }
        ]
        return PlanComposeResult(itinerary=itinerary, tradeoffs=tradeoffs, steps=steps)
