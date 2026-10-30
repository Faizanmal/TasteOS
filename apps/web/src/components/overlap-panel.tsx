import type { OverlapReport } from "@/lib/overlap";

export function OverlapPanel({ report }: { report: OverlapReport }) {
  return (
    <section className="overlap-panel" aria-label="Taste overlap">
      <div className="meta">Local overlap · {report.method}</div>
      <h2>Where tastes meet</h2>
      <p className="muted">
        Computed from selected profile favorites and preferences only — not a
        Qloo score.
      </p>

      <div className="overlap-grid">
        <div>
          <h3>Shared signals</h3>
          {report.shared.length === 0 ? (
            <p className="muted">No shared tokens across all three profiles.</p>
          ) : (
            <div className="tags">
              {report.shared.map((item) => (
                <span className="tag shared" key={item}>
                  {item}
                </span>
              ))}
            </div>
          )}
        </div>
        <div>
          <h3>Hard exclusions in play</h3>
          {report.exclusionHits.length === 0 ? (
            <p className="muted">No entity exclusions listed.</p>
          ) : (
            <ul className="taste-list">
              {report.exclusionHits.map((id) => (
                <li key={id}>
                  <code>{id}</code>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      <div className="comparison overlap-unique">
        {report.uniqueByProfile.map((row, index) => (
          <div key={row.id}>
            <div className="meta">Unique to {row.name}</div>
            <ul className="taste-list">
              {row.unique.length === 0 ? (
                <li>Fully overlapping with the group</li>
              ) : (
                row.unique.map((item) => <li key={item}>{item}</li>)
              )}
            </ul>
            <span className="profile-index subtle">0{index + 1}</span>
          </div>
        ))}
      </div>
    </section>
  );
}
