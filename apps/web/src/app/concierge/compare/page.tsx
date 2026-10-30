"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { ModeBanner } from "@/components/mode-banner";
import { OverlapPanel } from "@/components/overlap-panel";
import { Profile, profileLabel, profileTasteTags } from "@/lib/api";
import { computeTasteOverlap } from "@/lib/overlap";
import { clearPlanCache, readProfiles } from "@/lib/session";

export default function ComparePage() {
  const router = useRouter();
  const [profiles] = useState<Profile[]>(() => readProfiles());
  const overlap = useMemo(
    () => (profiles.length ? computeTasteOverlap(profiles) : null),
    [profiles],
  );

  function goToResults() {
    clearPlanCache();
    router.push("/concierge/results");
  }

  return (
    <main className="page-shell">
      <ModeBanner />
      <header className="page-heading">
        <div>
          <div className="step">03 / Read the room</div>
          <h1>Group taste comparison.</h1>
        </div>
        <p>
          Shared signals, unique edges, and hard exclusions stay visible before
          TasteOS proposes a plan. Difference is context—not noise to average
          away.
        </p>
      </header>

      {profiles.length !== 3 ? (
        <div className="notice" role="status">
          No complete group is selected.{" "}
          <Link href="/concierge">
            <strong>Choose three profiles first.</strong>
          </Link>
        </div>
      ) : (
        <>
          <div className="comparison">
            {profiles.map((profile, index) => (
              <div key={profile.id}>
                <div className="meta">Profile 0{index + 1}</div>
                <h2>{profileLabel(profile)}</h2>
                <ul className="taste-list">
                  {profileTasteTags(profile).map((entry) => (
                    <li key={entry}>{entry}</li>
                  ))}
                  {(profile.exclusions || []).length > 0 && (
                    <li>
                      Exclusions: {(profile.exclusions || []).join(", ")}
                    </li>
                  )}
                </ul>
              </div>
            ))}
          </div>

          {overlap && <OverlapPanel report={overlap} />}

          <div className="actions">
            <button className="button" type="button" onClick={goToResults}>
              Build the group plan <span aria-hidden="true">→</span>
            </button>
            <Link className="button secondary" href="/concierge/edit">
              Edit preferences
            </Link>
            <Link className="button secondary" href="/concierge">
              Change group
            </Link>
          </div>
        </>
      )}
    </main>
  );
}
