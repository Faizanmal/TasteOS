import type { Candidate } from "@/lib/api";
import type { ReactNode } from "react";

type Props = {
  candidate: Candidate;
  variant?: "primary" | "alt";
  index?: number;
  actions?: ReactNode;
};

export function CandidateCard({
  candidate,
  variant = "alt",
  index = 0,
  actions,
}: Props) {
  const isPrimary = variant === "primary";
  const Heading = isPrimary ? "h2" : "h3";

  return (
    <article className={`result-card ${isPrimary ? "primary" : ""}`}>
      <div className="meta">
        {isPrimary ? "Primary pick" : `Alternative 0${index + 1}`}
        {" · "}
        {candidate.source || "unknown source"}
      </div>
      <Heading>{candidate.name}</Heading>
      {candidate.category && <p className="meta">{candidate.category}</p>}
      <p className="muted">
        {candidate.description ||
          candidate.match_explanation ||
          "No description returned."}
      </p>
      <p className="meta">
        TasteOS app rank{" "}
        {candidate.app_rank_score != null
          ? candidate.app_rank_score.toFixed(2)
          : "—"}
        {candidate.qloo_affinity != null
          ? ` · Retrieved Qloo affinity ${candidate.qloo_affinity.toFixed(2)}`
          : " · No live Qloo affinity"}
      </p>
      {(candidate.evidence_refs || []).length > 0 && (
        <div className="evidence-block">
          <div className="meta">Evidence refs</div>
          <ul className="taste-list">
            {(candidate.evidence_refs || []).slice(0, 6).map((ref) => (
              <li key={ref}>{ref}</li>
            ))}
          </ul>
        </div>
      )}
      {actions}
    </article>
  );
}
