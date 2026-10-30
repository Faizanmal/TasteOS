"""Negotiation Engine — transparent, deterministic group ranking.

Scoring is APPLICATION logic. Qloo affinities (when present) are evidence inputs,
never renamed as group consensus scores.

## Method `tasteos_negotiation_v1`

### Inputs (per candidate × participant)
- Hard exclusions (entity ids) → status `excluded`, app_score `0`
- Soft anti-preferences (`avoid X` / `no X` matching tags) → status `conflict`, low score
- Supporting evidence (preference/tag overlap, Qloo explainability entity ids, demo food heuristic)
  → status `supported`, deterministic app_score in (0, 1]
- Otherwise → status `unknown`, app_score `None` (neutral 0.5 when aggregating; never fabricated affinity)

### Normalization
- Per-participant `app_score` clamped to `[0, 1]`
- Unknown participants contribute neutral `0.5` to the group mean (documented; not a claimed preference)
- Live `qloo_affinity` may blend into individual support (`0.7 * app + 0.3 * affinity`) and add a
  **capped** group component `0.15 * affinity` so one-person popularity cannot dominate

### Group formula
```
app_rank_score =
    0.45 * fairness          # 1 - (max(known) - min(known)) among non-excluded known scores
  + 0.35 * mean_support      # mean of per-participant contributions (unknown→0.5)
  + 0.15 * coverage          # (#supported) / n_participants
  + 0.05 * diversity_norm    # min(1, tag_count * 0.25) from candidate tags
  + qloo_component           # 0.15 * affinity in live mode only, else 0
```
Result clamped to `[0, 1]`, rounded to 4 decimals. Sort: `-app_rank_score`, then name.

### Limitations
- Does not claim Qloo guarantees consensus
- Demo heuristics are labeled (`demo_heuristic:…`) and affinities are wiped in demo responses
- Missing evidence is `unknown`, never invented
"""

from __future__ import annotations

from dataclasses import dataclass, field
from statistics import mean

from app.agents.candidate_retriever import RetrievedCandidate
from app.agents.profile_resolver import ResolvedProfile
from app.schemas.recommendation import CandidateOut, ParticipantMatch

METHOD = "tasteos_negotiation_v1"


@dataclass
class NegotiationResult:
    ranked: list[CandidateOut]
    steps: list[dict] = field(default_factory=list)


def _tag_names(entity_tags: list) -> set[str]:
    names: set[str] = set()
    for t in entity_tags:
        if getattr(t, "name", None):
            names.add(t.name.lower())
    return names


def _anti_preference_hits(preferences: list[str], entity_tags: set[str]) -> list[str]:
    """Detect soft conflicts from 'avoid X' / 'no X' preferences against tags."""
    hits: list[str] = []
    tag_blob = " ".join(entity_tags)
    for pref in preferences:
        pl = pref.lower().strip()
        token = ""
        if pl.startswith("avoid "):
            token = pl[6:].strip()
        elif pl.startswith("no "):
            token = pl[3:].strip()
        if token and (
            token in tag_blob or any(token in t or t in token for t in entity_tags)
        ):
            hits.append(pref)
    return hits


class NegotiationEngine:
    def rank(
        self,
        candidates: list[RetrievedCandidate],
        profiles: list[ResolvedProfile],
        *,
        mode: str,
    ) -> NegotiationResult:
        ranked: list[CandidateOut] = []
        n = max(len(profiles), 1)

        for cand in candidates:
            matches: list[ParticipantMatch] = []
            support_scores: list[float] = []
            entity_tags = _tag_names(cand.entity.tags)

            for profile in profiles:
                if cand.entity.entity_id in profile.exclusions:
                    matches.append(
                        ParticipantMatch(
                            profile_id=profile.id,
                            display_name=profile.display_name,
                            status="excluded",
                            evidence=[],
                            app_score=0.0,
                            qloo_affinity=None,
                            notes="Hard exclusion from this participant's profile.",
                        )
                    )
                    support_scores.append(0.0)
                    continue

                evidence: list[str] = []

                pref_hits = [
                    p
                    for p in profile.explicit_preferences
                    if p.lower() in " ".join(entity_tags)
                    or any(p.lower() in t or t in p.lower() for t in entity_tags)
                ]
                # Exclude anti-preferences from positive hits
                pref_hits = [
                    p
                    for p in pref_hits
                    if not p.lower().startswith("avoid ")
                    and not p.lower().startswith("no ")
                ]
                if pref_hits:
                    evidence.append(f"explicit_preference:{','.join(pref_hits)}")

                explain = cand.meta.get("explainability") or {}
                contrib_ids: set[str] = set()
                if isinstance(explain, dict):
                    for key in ("entities", "signal.interests.entities", "inputs"):
                        block = explain.get(key)
                        if isinstance(block, list):
                            for item in block:
                                if isinstance(item, dict) and item.get("entity_id"):
                                    contrib_ids.add(item["entity_id"])
                                elif isinstance(item, str):
                                    contrib_ids.add(item)

                overlapping_favs = [
                    fid for fid in profile.favorite_ids if fid in contrib_ids
                ]
                if overlapping_favs:
                    evidence.append(f"qloo_explainability:{','.join(overlapping_favs)}")

                for tag in entity_tags:
                    for fav in profile.favorites:
                        fav_name = (fav.get("name") or "").lower()
                        if fav_name and (tag in fav_name or fav_name in tag):
                            evidence.append(f"name_tag_overlap:{fav.get('name')}:{tag}")

                food_signal = any(
                    "bear" in (f.get("name") or "").lower()
                    or (f.get("entity_type") or "").endswith("tv_show")
                    for f in profile.favorites
                )
                if (
                    mode == "demo"
                    and food_signal
                    and cand.entity.subtype == "urn:entity:place"
                ):
                    evidence.append("demo_heuristic:food_culture_affinity")

                anti = _anti_preference_hits(profile.explicit_preferences, entity_tags)
                qloo_aff = cand.qloo_affinity if mode == "live" else None

                if anti and not evidence:
                    status = "conflict"
                    app_score = 0.15
                    evidence = [f"soft_conflict:{','.join(anti)}"]
                    notes = "Soft preference conflict (avoid/no …); not a hard entity exclusion."
                elif evidence:
                    status = "supported"
                    app_score = min(1.0, 0.4 + 0.15 * len(evidence))
                    if qloo_aff is not None:
                        app_score = min(1.0, 0.7 * app_score + 0.3 * float(qloo_aff))
                    notes = (
                        "Supported by retrieved evidence and/or transparent heuristics."
                    )
                else:
                    status = "unknown"
                    app_score = None
                    notes = (
                        "No supported preference evidence for this participant; "
                        "treated as unknown (not fabricated)."
                    )

                matches.append(
                    ParticipantMatch(
                        profile_id=profile.id,
                        display_name=profile.display_name,
                        status=status,
                        evidence=evidence,
                        app_score=app_score,
                        qloo_affinity=qloo_aff,
                        notes=notes,
                    )
                )
                if app_score is not None:
                    support_scores.append(app_score)
                else:
                    support_scores.append(0.5)  # neutral for unknown — documented

            known = [
                m.app_score
                for m in matches
                if m.app_score is not None and m.status not in {"excluded"}
            ]
            mean_support = mean(support_scores) if support_scores else 0.0
            gap = (max(known) - min(known)) if known else 0.0
            fairness = 1.0 - gap
            coverage = sum(1 for m in matches if m.status == "supported") / n
            diversity_bonus = min(0.2, 0.05 * len(entity_tags))
            diversity_norm = diversity_bonus / 0.2 if diversity_bonus else 0.0

            qloo_component = 0.0
            if mode == "live" and cand.qloo_affinity is not None:
                qloo_component = 0.15 * float(cand.qloo_affinity)

            app_rank = (
                0.45 * fairness
                + 0.35 * mean_support
                + 0.15 * coverage
                + 0.05 * diversity_norm
                + qloo_component
            )
            app_rank = max(0.0, min(1.0, app_rank))

            source = "qloo" if cand.source == "qloo" else "tasteos_demo_dataset"
            explanation_bits = []
            supported_names = [
                m.display_name for m in matches if m.status == "supported"
            ]
            unknown_names = [m.display_name for m in matches if m.status == "unknown"]
            excluded_names = [m.display_name for m in matches if m.status == "excluded"]
            conflict_names = [m.display_name for m in matches if m.status == "conflict"]
            if supported_names:
                explanation_bits.append(
                    f"Supported evidence for: {', '.join(supported_names)}."
                )
            if unknown_names:
                explanation_bits.append(
                    f"Unknown evidence for: {', '.join(unknown_names)}."
                )
            if conflict_names:
                explanation_bits.append(
                    f"Soft conflicts for: {', '.join(conflict_names)}."
                )
            if excluded_names:
                explanation_bits.append(
                    f"Hard exclusions for: {', '.join(excluded_names)}."
                )
            explanation_bits.append(
                "Rank score is TasteOS application logic; Qloo affinity (if any) is cited separately."
            )

            limitations = []
            if mode == "demo":
                limitations.append(
                    "Candidate originated from the labeled demo dataset, not live Qloo."
                )
            if any(m.status == "unknown" for m in matches):
                limitations.append(
                    "At least one participant has unknown evidence for this option."
                )
            if any(m.status == "conflict" for m in matches):
                limitations.append(
                    "At least one participant has a soft preference conflict."
                )

            ranked.append(
                CandidateOut(
                    entity_id=cand.entity.entity_id,
                    name=cand.entity.name,
                    category=cand.entity.subtype or "urn:entity",
                    description=cand.entity.description_text(),
                    image_url=cand.entity.image_url(),
                    source=source,  # type: ignore[arg-type]
                    qloo_affinity=cand.qloo_affinity if mode == "live" else None,
                    app_rank_score=round(app_rank, 4),
                    participant_matches=matches,
                    evidence_refs=[e for m in matches for e in m.evidence],
                    match_explanation=" ".join(explanation_bits),
                    limitations=limitations,
                    ranking_inputs={
                        "fairness": round(fairness, 4),
                        "mean_support": round(mean_support, 4),
                        "coverage": round(coverage, 4),
                        "diversity_bonus": round(diversity_bonus, 4),
                        "diversity_norm": round(diversity_norm, 4),
                        "qloo_component": round(qloo_component, 4),
                        "method": METHOD,
                        "weights": {
                            "fairness": 0.45,
                            "mean_support": 0.35,
                            "coverage": 0.15,
                            "diversity": 0.05,
                            "max_qloo_component": 0.15,
                        },
                    },
                )
            )

        ranked.sort(key=lambda c: (-c.app_rank_score, c.name.lower()))
        steps = [
            {
                "stage": "negotiate",
                "status": "ok",
                "method": METHOD,
                "candidate_count": len(ranked),
                "top": ranked[0].name if ranked else None,
            }
        ]
        return NegotiationResult(ranked=ranked, steps=steps)
