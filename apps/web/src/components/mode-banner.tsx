"use client";

import { useEffect, useState } from "react";
import { ApiMode, getMode } from "@/lib/api";

export function ModeBanner() {
  const [mode, setMode] = useState<ApiMode | null>(null);
  const [offline, setOffline] = useState(false);

  useEffect(() => {
    getMode()
      .then((m) => {
        setMode(m);
        setOffline(false);
      })
      .catch(() => setOffline(true));
  }, []);

  if (offline) {
    return (
      <div className="mode-banner offline" role="status">
        API offline — start the TasteOS backend to load plans.
      </div>
    );
  }

  if (!mode) {
    return (
      <div className="mode-banner" role="status">
        Checking API mode…
      </div>
    );
  }

  const isDemo = mode.mode === "demo";
  return (
    <div
      className={`mode-banner ${isDemo ? "demo" : "live"}`}
      role="status"
      title={mode.description}
    >
      <strong>{isDemo ? "Demo mode" : "Live mode"}</strong>
      <span>
        {isDemo
          ? "Results use the labeled TasteOS sample dataset — not a live Qloo request."
          : "Recommendations call Qloo Search + Insights server-side. Affinity is shown only when returned."}
      </span>
    </div>
  );
}
