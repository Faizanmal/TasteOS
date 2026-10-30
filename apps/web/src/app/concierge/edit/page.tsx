"use client";

import Link from "next/link";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { ModeBanner } from "@/components/mode-banner";
import {
  createProfile,
  Favorite,
  isDemoProfile,
  Profile,
  profileLabel,
  updateProfile,
} from "@/lib/api";
import { clearPlanCache, readProfiles, writeProfiles } from "@/lib/session";

type Draft = {
  display_name: string;
  preferencesText: string;
  exclusionsText: string;
  favoritesText: string;
};

function toDraft(profile: Profile): Draft {
  return {
    display_name: profile.display_name,
    preferencesText: (profile.explicit_preferences || []).join(", "),
    exclusionsText: (profile.exclusions || []).join(", "),
    favoritesText: (profile.favorites || [])
      .map((f) => f.name)
      .join(", "),
  };
}

function parseList(raw: string): string[] {
  return raw
    .split(",")
    .map((part) => part.trim())
    .filter(Boolean)
    .slice(0, 20);
}

function favoritesFromNames(
  names: string[],
  previous: Favorite[],
): Favorite[] {
  return names.map((name, index) => {
    const existing = previous.find(
      (f) => f.name.toLowerCase() === name.toLowerCase(),
    );
    if (existing) return existing;
    return {
      entity_id: `local-${index}-${name.toLowerCase().replace(/\s+/g, "-").slice(0, 40)}`,
      name,
      entity_type: "urn:entity:place",
    };
  });
}

function initialDrafts(profiles: Profile[]): Record<string, Draft> {
  const next: Record<string, Draft> = {};
  for (const profile of profiles) {
    next[profile.id] = toDraft(profile);
  }
  return next;
}

export default function EditPreferencesPage() {
  const router = useRouter();
  const [profiles, setProfiles] = useState<Profile[]>(() => readProfiles());
  const [drafts, setDrafts] = useState<Record<string, Draft>>(() =>
    initialDrafts(readProfiles()),
  );
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [status, setStatus] = useState("");

  function updateDraft(id: string, patch: Partial<Draft>) {
    setDrafts((current) => ({
      ...current,
      [id]: { ...current[id], ...patch },
    }));
  }

  async function saveAll() {
    if (profiles.length !== 3) {
      setError("Select three profiles on the setup screen first.");
      return;
    }
    setSaving(true);
    setError("");
    setStatus("");
    try {
      const saved: Profile[] = [];
      for (const profile of profiles) {
        const draft = drafts[profile.id];
        if (!draft?.display_name.trim()) {
          throw new Error(`Each profile needs a display name.`);
        }
        const body = {
          display_name: draft.display_name.trim(),
          explicit_preferences: parseList(draft.preferencesText),
          exclusions: parseList(draft.exclusionsText),
          favorites: favoritesFromNames(
            parseList(draft.favoritesText),
            profile.favorites || [],
          ),
        };

        if (isDemoProfile(profile)) {
          // Demo profiles are read-only on the API — clone into an anonymous profile.
          const cloned = await createProfile({
            ...body,
            preferred_domains: profile.preferred_domains?.length
              ? profile.preferred_domains
              : ["urn:entity:place"],
            notes: `Cloned from ${profile.id} for editable preferences.`,
          });
          saved.push(cloned);
        } else {
          const updated = await updateProfile(profile.id, body);
          saved.push(updated);
        }
      }
      writeProfiles(saved);
      clearPlanCache();
      setProfiles(saved);
      const next: Record<string, Draft> = {};
      for (const profile of saved) next[profile.id] = toDraft(profile);
      setDrafts(next);
      setStatus(
        "Preferences saved. Demo profiles were cloned to editable anonymous profiles when needed.",
      );
    } catch (reason) {
      setError(
        reason instanceof Error ? reason.message : "Could not save preferences.",
      );
    } finally {
      setSaving(false);
    }
  }

  function continueToCompare() {
    if (profiles.length !== 3) {
      setError("Need three profiles before comparing tastes.");
      return;
    }
    writeProfiles(profiles);
    router.push("/concierge/compare");
  }

  return (
    <main className="page-shell">
      <ModeBanner />
      <header className="page-heading">
        <div>
          <div className="step">02 / Tune the signals</div>
          <h1>Edit cultural preferences.</h1>
        </div>
        <p>
          Favorites, soft preferences, and hard exclusions. Demo profiles are
          cloned into anonymous editable copies when you save — no unnecessary
          personal data.
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
          {error && (
            <div className="notice error" role="alert">
              {error}
            </div>
          )}
          {status && (
            <div className="notice" role="status">
              {status}
            </div>
          )}

          <div className="editor-grid">
            {profiles.map((profile, index) => {
              const draft = drafts[profile.id] || toDraft(profile);
              return (
                <section
                  className="editor-card"
                  key={profile.id}
                  aria-label={`Edit ${profileLabel(profile)}`}
                >
                  <div className="meta">
                    Profile 0{index + 1}
                    {isDemoProfile(profile) ? " · Demo (clone on save)" : " · Custom"}
                  </div>
                  <div className="field">
                    <label htmlFor={`name-${profile.id}`}>Display name</label>
                    <input
                      id={`name-${profile.id}`}
                      value={draft.display_name}
                      onChange={(e) =>
                        updateDraft(profile.id, {
                          display_name: e.target.value,
                        })
                      }
                    />
                  </div>
                  <div className="field">
                    <label htmlFor={`fav-${profile.id}`}>
                      Favorite entities (comma-separated names)
                    </label>
                    <input
                      id={`fav-${profile.id}`}
                      value={draft.favoritesText}
                      onChange={(e) =>
                        updateDraft(profile.id, {
                          favoritesText: e.target.value,
                        })
                      }
                    />
                  </div>
                  <div className="field">
                    <label htmlFor={`pref-${profile.id}`}>
                      Soft preferences
                    </label>
                    <input
                      id={`pref-${profile.id}`}
                      value={draft.preferencesText}
                      onChange={(e) =>
                        updateDraft(profile.id, {
                          preferencesText: e.target.value,
                        })
                      }
                      placeholder="e.g. comfort food, walkable neighborhood"
                    />
                  </div>
                  <div className="field">
                    <label htmlFor={`excl-${profile.id}`}>
                      Hard exclusions (entity ids)
                    </label>
                    <input
                      id={`excl-${profile.id}`}
                      value={draft.exclusionsText}
                      onChange={(e) =>
                        updateDraft(profile.id, {
                          exclusionsText: e.target.value,
                        })
                      }
                      placeholder="e.g. demo-place-katzs"
                    />
                  </div>
                </section>
              );
            })}
          </div>

          <div className="actions">
            <button
              className="button"
              type="button"
              disabled={saving}
              onClick={() => void saveAll()}
            >
              {saving ? "Saving…" : "Save preferences"}
            </button>
            <button
              className="button secondary"
              type="button"
              onClick={continueToCompare}
            >
              Compare tastes <span aria-hidden="true">→</span>
            </button>
            <Link className="button secondary" href="/concierge">
              Back to setup
            </Link>
          </div>
        </>
      )}
    </main>
  );
}
