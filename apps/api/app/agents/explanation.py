"""Explanation Generator — copy grounded in retrieved evidence vs application logic.

Never invent Qloo affinities or claim consensus is guaranteed by Qloo.
"""

from __future__ import annotations

from app.schemas.recommendation import CandidateOut, ParticipantMatch

BOOKING_DISCLAIMER = (
    "This itinerary is a proposed plan only. TasteOS does not confirm reservations, "
    "availability, tickets, or bookings."
)


class ExplanationGenerator:
    def group_summary(
        self, primary: CandidateOut, reconciliation: list[ParticipantMatch]
    ) -> str:
        supported = [m.display_name for m in reconciliation if m.status == "supported"]
        unknown = [m.display_name for m in reconciliation if m.status == "unknown"]
        excluded = [m.display_name for m in reconciliation if m.status == "excluded"]
        conflicted = [m.display_name for m in reconciliation if m.status == "conflict"]
        parts = [
            f"{primary.name} leads with TasteOS app rank {primary.app_rank_score:.2f}."
        ]
        if primary.qloo_affinity is not None:
            parts.append(
                f"Retrieved Qloo affinity (not a consensus score): {primary.qloo_affinity:.2f}."
            )
        else:
            parts.append("No live Qloo affinity available for this candidate.")
        if supported:
            parts.append(f"Evidence-backed fit: {', '.join(supported)}.")
        if unknown:
            parts.append(f"Unknown evidence (not fabricated): {', '.join(unknown)}.")
        if conflicted:
            parts.append(f"Soft preference conflicts: {', '.join(conflicted)}.")
        if excluded:
            parts.append(f"Hard exclusions: {', '.join(excluded)}.")
        parts.append("Qloo does not guarantee group consensus.")
        return " ".join(parts)

    def selection_rationale(self, primary: CandidateOut) -> str:
        """Explain selection using ranking_inputs + evidence refs (application layer)."""
        inputs = primary.ranking_inputs or {}
        method = inputs.get("method", "tasteos_negotiation_v1")
        bits = [
            f"Selected by {method}.",
            f"fairness={inputs.get('fairness')}",
            f"mean_support={inputs.get('mean_support')}",
            f"coverage={inputs.get('coverage')}",
        ]
        if inputs.get("qloo_component"):
            bits.append(
                f"capped_qloo_component={inputs.get('qloo_component')} "
                "(retrieved affinity input only)."
            )
        if primary.evidence_refs:
            bits.append(f"Evidence refs: {', '.join(primary.evidence_refs[:6])}.")
        else:
            bits.append(
                "No participant-linked evidence refs; unknowns treated neutrally."
            )
        bits.append(primary.match_explanation)
        return " ".join(str(b) for b in bits if b is not None)

    def tradeoff_summary(
        self,
        primary: CandidateOut,
        alternatives: list[CandidateOut],
    ) -> str:
        alt_names = ", ".join(a.name for a in alternatives[:3]) or "none"
        return (
            f"Primary pick balances fairness and coverage rather than maximizing one person. "
            f"Next alternatives: {alt_names}. "
            f"{self.group_summary(primary, primary.participant_matches)}"
        )

    def evidence_vs_explanation_note(self) -> str:
        return (
            "participant_matches[].evidence and evidence_refs are retrieved or rule-matched signals; "
            "match_explanation / tradeoffs / selection_rationale are TasteOS-generated explanations."
        )
