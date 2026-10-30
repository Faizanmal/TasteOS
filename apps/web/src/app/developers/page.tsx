import { API_BASE_URL } from "@/lib/api";
import { ModeBanner } from "@/components/mode-banner";

const endpoints = [
  ["GET", "/api/v1/mode", "Inspect runtime mode and Qloo key presence (boolean)."],
  ["GET", "/api/v1/profiles/demo", "Curated anonymous demo profiles."],
  ["POST", "/api/v1/profiles", "Create an anonymous taste profile."],
  ["PATCH", "/api/v1/profiles/{id}", "Update preferences / exclusions."],
  ["POST", "/api/v1/recommendations", "Core recommendations for profile ids."],
  ["POST", "/api/v1/concierge/plan", "Reconcile profiles into a proposed outing."],
  ["POST", "/api/v1/concierge/plan/{id}/reject", "Reject one entity and regenerate."],
  ["GET", "/api/v1/concierge/plan/{id}", "Fetch a persisted plan payload."],
];

export default function DevelopersPage() {
  return (
    <main className="page-shell">
      <ModeBanner />
      <header className="page-heading">
        <div>
          <div className="step">TasteOS / API</div>
          <h1>Culture, as infrastructure.</h1>
        </div>
        <p>
          Add culturally aware recommendations to an agent without exposing
          credentials in the browser. Your backend calls the TasteOS API; the
          browser only sees public JSON.
        </p>
      </header>

      <div className="dev-layout">
        <aside>
          <div className="meta">API base</div>
          <p>
            <code>{API_BASE_URL}</code>
          </p>
          <p className="muted">
            Configure with <code>NEXT_PUBLIC_API_BASE_URL</code>. Qloo keys stay
            on the API host — never in this Next.js bundle.
          </p>
          <div className="actions">
            <a
              className="button"
              href={`${API_BASE_URL}/docs`}
              target="_blank"
              rel="noreferrer"
            >
              Open API docs <span aria-hidden="true">↗</span>
            </a>
          </div>
        </aside>
        <section aria-label="API endpoints">
          {endpoints.map(([method, path, description]) => (
            <div className="endpoint" key={path}>
              <span className="method">{method}</span>
              <div>
                <code>{path}</code>
                <p className="muted">{description}</p>
              </div>
            </div>
          ))}
          <div className="notice">
            Responses report their own <strong>mode</strong> and{" "}
            <strong>source</strong>. Treat those fields as authoritative; demo
            data is never presented as live Qloo output.{" "}
            <code>app_rank_score</code> is TasteOS negotiation;{" "}
            <code>qloo_affinity</code> is retrieved evidence when present.
          </div>
        </section>
      </div>
    </main>
  );
}
