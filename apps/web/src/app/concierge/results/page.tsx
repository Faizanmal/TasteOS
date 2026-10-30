"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { CandidateCard } from "@/components/candidate-card";
import { ModeBanner } from "@/components/mode-banner";
import {
  ConciergePlan,
  createPlan,
  PipelineStage,
  Profile,
  rejectCandidate,
} from "@/lib/api";
import {
  readConstraints,
  readPlanCache,
  readProfiles,
  writePlanCache,
} from "@/lib/session";

function entityId(candidate: { entity_id?: string } | null | undefined) {
  return candidate?.entity_id || "";
}

export default function ResultsPage() {
  const [plan, setPlan] = useState<ConciergePlan | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [rejecting, setRejecting] = useState(false);

  const loadPlan = useCallback(async (force = false) => {
    setError("");
    setLoading(true);
    try {
      if (!force) {
        const cached = readPlanCache<ConciergePlan>();
        if (cached?.primary) {
          setPlan(cached);
          return;
        }
      }
      const profiles = readProfiles();
      const constraints = readConstraints();
      if (profiles.length !== 3) {
        throw new Error("Choose three profiles before requesting a plan.");
      }
      const result = await createPlan({
        profile_ids: profiles.map((profile: Profile) => profile.id),
        target_domain: "urn:entity:place",
        location_query: constraints.location || "New York",
        experience: constraints.experience || "evening_out",
        budget: constraints.budget || "any",
        take: 6,
        alternatives_count: 3,
      });
      setPlan(result);
      writePlanCache(result);
    } catch (reason) {
      setError(
        reason instanceof Error ? reason.message : "Could not create the plan.",
      );
      setPlan(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    queueMicrotask(() => {
      void loadPlan(false);
    });
  }, [loadPlan]);

  async function rejectPrimary() {
    if (!plan?.primary) return;
    const id = entityId(plan.primary);
    if (!id) {
      setError("This recommendation has no entity ID and cannot be rejected.");
      return;
    }
    setRejecting(true);
    setError("");
    try {
      const updated = await rejectCandidate(plan.id, id);
      setPlan(updated);
      writePlanCache(updated);
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "Could not reject this recommendation.",
      );
    } finally {
      setRejecting(false);
    }
  }

  const stages: PipelineStage[] = Array.isArray(plan?.pipeline)
    ? plan.pipeline
    : [];

  return (
    <main className="page-shell">
      <ModeBanner />
      <header className="page-heading">
        <div>
          <div className="step">04 / The considered answer</div>
          <h1>Recommendations & itinerary.</h1>
        </div>
        <p>
          Primary pick, alternatives, evidence, and trade-offs. Application
          ranking stays distinct from retrieved Qloo affinity. Plans are
          proposals — never bookings.
        </p>
      </header>

      {error && (
        <div className="notice error" role="alert">
          {error}
        </div>
      )}
      {loading ? (
        <p className="loading" aria-live="polite">
          Reconciling the group’s cultural signals…
        </p>
      ) : !plan ? (
        <div className="actions">
          <button
            className="button"
            type="button"
            onClick={() => void loadPlan(true)}
          >
            Try again
          </button>
          <Link className="button secondary" href="/concierge">
            Edit group
          </Link>
        </div>
      ) : (
        <>
          <div className="meta plan-mode-line">
            {plan.mode} mode · experience {plan.experience || "—"}
            {(plan.rejected_entity_ids || []).length > 0
              ? ` · rejected ${plan.rejected_entity_ids?.length}`
              : ""}
          </div>

          {plan.disclaimer && (
            <div className="notice" role="note">
              {plan.disclaimer}
            </div>
          )}

          <div className="result-grid">
            <CandidateCard
              candidate={plan.primary}
              variant="primary"
              actions={
                <div className="actions">
                  <button
                    className="button secondary"
                    type="button"
                    onClick={() => void rejectPrimary()}
                    disabled={rejecting}
                  >
                    {rejecting ? "Finding another…" : "Reject & regenerate"}
                  </button>
                </div>
              }
            />
            <div className="stack">
              {(plan.alternatives || []).map((candidate, index) => (
                <CandidateCard
                  key={entityId(candidate) || index}
                  candidate={candidate}
                  variant="alt"
                  index={index}
                />
              ))}
              {(plan.alternatives || []).length === 0 && (
                <div className="notice" role="status">
                  No alternatives returned for this request.
                </div>
              )}
            </div>
          </div>

          {plan.selection_rationale && (
            <section className="data-section">
              <h2>Selection rationale</h2>
              <p className="muted">{plan.selection_rationale}</p>
            </section>
          )}

          {stages.length > 0 && (
            <section className="data-section">
              <h2>Planning process</h2>
              <div className="pipeline" aria-label="Pipeline stages">
                {stages.map((stage, index) => (
                  <div className="stage" key={`${stage.stage}-${index}`}>
                    <strong>{stage.stage || `Stage ${index + 1}`}</strong>
                    <span>{stage.status || "ok"}</span>
                  </div>
                ))}
              </div>
            </section>
          )}

          <section className="data-section">
            <h2>Per-person evidence</h2>
            <div className="data-list">
              {(plan.reconciliation || []).map((match) => (
                <div className="data-row" key={match.profile_id}>
                  <strong>
                    {match.display_name} · {match.status}
                  </strong>
                  <span>
                    {match.notes}
                    {match.evidence?.length
                      ? ` Evidence: ${match.evidence.join(", ")}`
                      : " Evidence: none (unknown not fabricated)"}
                    {match.app_score == null
                      ? " · App score: unknown"
                      : ` · App score: ${match.app_score.toFixed(2)}`}
                    {match.qloo_affinity != null
                      ? ` · Qloo affinity: ${match.qloo_affinity.toFixed(2)}`
                      : ""}
                  </span>
                </div>
              ))}
            </div>
          </section>

          <section className="data-section">
            <h2>Proposed itinerary</h2>
            <div className="data-list">
              {(plan.itinerary || []).map((stop) => (
                <div className="data-row" key={stop.order}>
                  <strong>
                    {stop.order}. {stop.title}
                    {stop.is_proposed ? " · proposed" : ""}
                  </strong>
                  <span>{stop.detail}</span>
                </div>
              ))}
            </div>
          </section>

          <section className="data-section">
            <h2>Trade-offs</h2>
            <p className="muted">{plan.tradeoffs}</p>
          </section>

          {(plan.limitations || []).length > 0 && (
            <section className="data-section">
              <h2>Limitations</h2>
              <ul className="taste-list">
                {plan.limitations.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </section>
          )}

          <div className="actions">
            <button
              className="button secondary"
              type="button"
              onClick={() => void loadPlan(true)}
            >
              Refresh plan
            </button>
            <Link className="button secondary" href="/concierge/compare">
              Back to comparison
            </Link>
            <Link className="button secondary" href="/concierge">
              Start over
            </Link>
          </div>
        </>
      )}
    </main>
  );
}
