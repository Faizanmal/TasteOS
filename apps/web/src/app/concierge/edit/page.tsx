"use client";

import Link from "next/link";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { ModeBanner } from "@/components/mode-banner";
import {
  createProfile,
  Favorite,
  favoriteFromSearch,
  favoritesForApi,
  isDemoProfile,
  isQlooEntityId,
  isUnresolvedFavorite,
  Profile,
  profileLabel,
  searchEntities,
  SearchEntity,
  unresolvedFavorite,
  updateProfile,
} from "@/lib/api";
import { clearPlanCache, readProfiles, writeProfiles } from "@/lib/session";

type Draft = {
  display_name: string;
  preferencesText: string;
  exclusionsText: string;
  favorites: Favorite[];
  favoriteInput: string;
};

type PendingPick = {
  profileId: string;
  query: string;
  results: SearchEntity[];
};

function normalizeFavorite(favorite: Favorite): Favorite {
  if (isQlooEntityId(favorite.entity_id)) {
    return { ...favorite, unresolved: false };
  }
  if (favorite.entity_id.startsWith("demo-")) {
    // Demo seed IDs are fine in demo mode; live backend resolves them.
    return { ...favorite, unresolved: false };
  }
  return { ...favorite, unresolved: true };
}

function toDraft(profile: Profile): Draft {
  return {
    display_name: profile.display_name,
    preferencesText: (profile.explicit_preferences || []).join(", "),
    exclusionsText: (profile.exclusions || []).join(", "),
    favorites: (profile.favorites || []).map(normalizeFavorite),
    favoriteInput: "",
  };
}

function parseList(raw: string): string[] {
  return raw
    .split(",")
    .map((part) => part.trim())
    .filter(Boolean)
    .slice(0, 20);
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
  const [resolvingId, setResolvingId] = useState<string | null>(null);
  const [pendingPick, setPendingPick] = useState<PendingPick | null>(null);

  function updateDraft(id: string, patch: Partial<Draft>) {
    setDrafts((current) => ({
      ...current,
      [id]: { ...current[id], ...patch },
    }));
  }

  function removeFavorite(profileId: string, entityId: string) {
    const draft = drafts[profileId];
    if (!draft) return;
    updateDraft(profileId, {
      favorites: draft.favorites.filter((f) => f.entity_id !== entityId),
    });
    if (pendingPick?.profileId === profileId) {
      setPendingPick(null);
    }
  }

  function commitFavorite(profileId: string, favorite: Favorite) {
    const draft = drafts[profileId];
    if (!draft) return;
    const exists = draft.favorites.some(
      (f) =>
        f.entity_id === favorite.entity_id ||
        f.name.toLowerCase() === favorite.name.toLowerCase(),
    );
    if (exists) {
      updateDraft(profileId, {
        favorites: draft.favorites.map((f) =>
          f.name.toLowerCase() === favorite.name.toLowerCase() ? favorite : f,
        ),
        favoriteInput: "",
      });
    } else {
      updateDraft(profileId, {
        favorites: [...draft.favorites, favorite].slice(0, 20),
        favoriteInput: "",
      });
    }
    setPendingPick(null);
  }

  async function resolveAndAddFavorite(profileId: string) {
    const draft = drafts[profileId];
    const query = draft?.favoriteInput.trim() || "";
    if (!query) return;

    setResolvingId(profileId);
    setError("");
    setPendingPick(null);
    try {
      const response = await searchEntities(query, 6);
      const results = response.results || [];
      if (results.length === 0) {
        commitFavorite(profileId, unresolvedFavorite(query));
        setStatus(
          `"${query}" was saved without a Qloo ID — it will not influence recommendations.`,
        );
        return;
      }
      if (results.length === 1) {
        commitFavorite(profileId, favoriteFromSearch(results[0]));
        return;
      }
      // Multiple matches: auto-highlight top, let the user confirm or pick another.
      setPendingPick({ profileId, query, results });
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "Could not search for that favorite.",
      );
    } finally {
      setResolvingId(null);
    }
  }

  function pickSearchResult(entity: SearchEntity) {
    if (!pendingPick) return;
    commitFavorite(pendingPick.profileId, favoriteFromSearch(entity));
  }

  function acceptTopMatch() {
    if (!pendingPick?.results[0]) return;
    pickSearchResult(pendingPick.results[0]);
  }

  function keepUnresolvedFromPick() {
    if (!pendingPick) return;
    commitFavorite(
      pendingPick.profileId,
      unresolvedFavorite(pendingPick.query),
    );
    setStatus(
      `"${pendingPick.query}" was saved without a Qloo ID — it will not influence recommendations.`,
    );
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
          favorites: favoritesForApi(draft.favorites),
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
      setPendingPick(null);
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
          Favorites resolve through Qloo search so live plans use real entity
          IDs. Demo profiles are cloned into anonymous editable copies when you
          save — no unnecessary personal data.
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
              const unresolvedCount = draft.favorites.filter((f) =>
                isUnresolvedFavorite(f),
              ).length;
              const showPicker = pendingPick?.profileId === profile.id;
              return (
                <section
                  className="editor-card"
                  key={profile.id}
                  aria-label={`Edit ${profileLabel(profile)}`}
                >
                  <div className="meta">
                    Profile 0{index + 1}
                    {isDemoProfile(profile)
                      ? " · Demo (clone on save)"
                      : " · Custom"}
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
                      Favorite entities
                    </label>
                    <div className="favorite-chips" aria-live="polite">
                      {draft.favorites.length === 0 ? (
                        <span className="favorite-empty">No favorites yet</span>
                      ) : (
                        draft.favorites.map((fav) => {
                          const unresolved = isUnresolvedFavorite(fav);
                          return (
                            <span
                              className={
                                unresolved
                                  ? "favorite-chip unresolved"
                                  : "favorite-chip"
                              }
                              key={`${fav.entity_id}-${fav.name}`}
                            >
                              <span>{fav.name}</span>
                              <button
                                type="button"
                                className="favorite-chip-remove"
                                aria-label={`Remove ${fav.name}`}
                                onClick={() =>
                                  removeFavorite(profile.id, fav.entity_id)
                                }
                              >
                                ×
                              </button>
                            </span>
                          );
                        })
                      )}
                    </div>
                    {unresolvedCount > 0 && (
                      <p className="favorite-hint">
                        {unresolvedCount === 1
                          ? "1 favorite has no Qloo ID and will not influence recommendations."
                          : `${unresolvedCount} favorites have no Qloo ID and will not influence recommendations.`}
                      </p>
                    )}
                    <div className="favorite-add-row">
                      <input
                        id={`fav-${profile.id}`}
                        value={draft.favoriteInput}
                        onChange={(e) =>
                          updateDraft(profile.id, {
                            favoriteInput: e.target.value,
                          })
                        }
                        onKeyDown={(e) => {
                          if (e.key === "Enter") {
                            e.preventDefault();
                            void resolveAndAddFavorite(profile.id);
                          }
                        }}
                        placeholder="e.g. Radiohead"
                        disabled={resolvingId === profile.id}
                      />
                      <button
                        className="button secondary favorite-add-btn"
                        type="button"
                        disabled={
                          saving ||
                          resolvingId === profile.id ||
                          !draft.favoriteInput.trim()
                        }
                        onClick={() => void resolveAndAddFavorite(profile.id)}
                      >
                        {resolvingId === profile.id ? "…" : "Add"}
                      </button>
                    </div>
                    {showPicker && pendingPick && (
                      <div className="favorite-picker" role="listbox">
                        <p className="favorite-hint">
                          Multiple matches — pick one, or use the top result.
                        </p>
                        <ul>
                          {pendingPick.results.map((result, i) => (
                            <li key={result.entity_id}>
                              <button
                                type="button"
                                className={
                                  i === 0
                                    ? "favorite-pick-option top"
                                    : "favorite-pick-option"
                                }
                                onClick={() => pickSearchResult(result)}
                              >
                                <strong>{result.name}</strong>
                                <span>
                                  {result.subtype || result.type || "entity"}
                                </span>
                              </button>
                            </li>
                          ))}
                        </ul>
                        <div className="favorite-picker-actions">
                          <button
                            type="button"
                            className="button"
                            onClick={acceptTopMatch}
                          >
                            Use top match
                          </button>
                          <button
                            type="button"
                            className="button secondary"
                            onClick={keepUnresolvedFromPick}
                          >
                            Keep name only
                          </button>
                        </div>
                      </div>
                    )}
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
