"""Constraint Evaluator — hard filters before ranking."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.agents.candidate_retriever import RetrievedCandidate
from app.agents.profile_resolver import ResolvedProfile


@dataclass
class ConstraintResult:
    kept: list[RetrievedCandidate]
    removed: list[dict]
    steps: list[dict] = field(default_factory=list)


class ConstraintEvaluator:
    def evaluate(
        self,
        candidates: list[RetrievedCandidate],
        profiles: list[ResolvedProfile],
        *,
        exclusions: list[str],
        rejected_entity_ids: list[str],
        budget: str | None = "any",
    ) -> ConstraintResult:
        hard_exclusions = set(exclusions) | set(rejected_entity_ids)
        for profile in profiles:
            hard_exclusions |= profile.exclusions

        kept: list[RetrievedCandidate] = []
        removed: list[dict] = []

        for cand in candidates:
            eid = cand.entity.entity_id
            if eid in hard_exclusions:
                removed.append(
                    {
                        "entity_id": eid,
                        "name": cand.entity.name,
                        "reason": "hard_exclusion_or_rejection",
                    }
                )
                continue

            # Budget is an application soft-hard filter using tag heuristics only.
            if budget and budget != "any":
                tags = {
                    ((t.name or "") + " " + (t.type or "")).lower()
                    for t in cand.entity.tags
                }
                tag_blob = " ".join(tags)
                if budget == "casual" and "fine dining" in tag_blob:
                    removed.append(
                        {
                            "entity_id": eid,
                            "name": cand.entity.name,
                            "reason": "budget_casual_excludes_fine_dining",
                        }
                    )
                    continue
                if budget == "upscale" and any(x in tag_blob for x in ("deli", "cafe")):
                    removed.append(
                        {
                            "entity_id": eid,
                            "name": cand.entity.name,
                            "reason": "budget_upscale_excludes_casual_tags",
                        }
                    )
                    continue

            kept.append(cand)

        steps = [
            {
                "stage": "constraint_evaluate",
                "status": "ok",
                "input_count": len(candidates),
                "kept_count": len(kept),
                "removed_count": len(removed),
                "hard_exclusion_count": len(hard_exclusions),
            }
        ]
        return ConstraintResult(kept=kept, removed=removed, steps=steps)
