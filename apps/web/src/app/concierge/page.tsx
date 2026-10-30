"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ModeBanner } from "@/components/mode-banner";
import {
  createProfile,
  getDemoProfiles,
  isDemoProfile,
  Profile,
  profileLabel,
  profileTasteTags,
} from "@/lib/api";
import {
  clearPlanCache,
  DEFAULT_CONSTRAINTS,
  writeConstraints,
  writeProfiles,
} from "@/lib/session";

const EXPERIENCES = [
  { value: "evening_out", label: "Evening out" },
  { value: "dinner", label: "Dinner" },
  { value: "drinks", label: "Drinks" },
  { value: "culture_night", label: "Culture night" },
] as const;

export default function ConciergeSetup() {
  const router = useRouter();
  const [profiles, setProfiles] = useState<Profile[]>([]);
  const [selected, setSelected] = useState<string[]>([]);
  const [location, setLocation] = useState(DEFAULT_CONSTRAINTS.location);
  const [experience, setExperience] =
    useState<(typeof EXPERIENCES)[number]["value"]>("evening_out");
  const [budget, setBudget] = useState<"any" | "casual" | "mid" | "upscale">(
    "any",
  );
  const [error, setError] = useState("");
  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState("");

  useEffect(() => {
    getDemoProfiles()
      .then(setProfiles)
      .catch((reason: Error) => setError(reason.message));
  }, []);

  function toggle(id: string) {
    setSelected((current) =>
      current.includes(id)
        ? current.filter((item) => item !== id)
        : current.length < 3
          ? [...current, id]
          : current,
    );
  }

  async function handleCreateProfile() {
    const name = newName.trim();
    if (!name) {
      setError("Enter a nickname for the new anonymous profile.");
      return;
    }
    setCreating(true);
    setError("");
    try {
      const created = await createProfile({
        display_name: name,
        favorites: [],
        explicit_preferences: [],
        exclusions: [],
        preferred_domains: ["urn:entity:place"],
      });
      setProfiles((current) => [...current, created]);
      setSelected((current) =>
        current.length < 3 ? [...current, created.id] : current,
      );
      setNewName("");
    } catch (reason) {
      setError(
        reason instanceof Error ? reason.message : "Could not create profile.",
      );
    } finally {
      setCreating(false);
    }
  }

  function continueToEditor() {
    const chosen = profiles.filter((profile) => selected.includes(profile.id));
    if (chosen.length !== 3) {
      setError("Select exactly three profiles to continue.");
      return;
    }
    writeProfiles(chosen);
    writeConstraints({ location, experience, budget });
    clearPlanCache();
    router.push("/concierge/edit");
  }

  return (
    <main className="page-shell">
      <ModeBanner />
      <header className="page-heading">
        <div>
          <div className="step">01 / Assemble the table</div>
          <h1>Who are we planning for?</h1>
        </div>
        <p>
          Select three demo profiles, or create anonymous nicknames. TasteOS
          looks for overlap without flattening what makes each person distinct.
        </p>
      </header>

      {error ? (
        <div className="notice error" role="alert">
          <strong>Something needs attention.</strong>
          <br />
          {error}
        </div>
      ) : null}

      {!error && profiles.length === 0 ? (
        <p className="loading" aria-live="polite">
          Gathering demo profiles…
        </p>
      ) : (
        <div className="profile-grid" aria-label="Selectable profiles">
          {profiles.map((profile, index) => {
            const isSelected = selected.includes(profile.id);
            const tastes = profileTasteTags(profile);
            return (
              <button
                type="button"
                className={`profile-card ${isSelected ? "selected" : ""}`}
                key={profile.id}
                onClick={() => toggle(profile.id)}
                aria-pressed={isSelected}
                aria-label={`${isSelected ? "Deselect" : "Select"} ${profileLabel(profile)}`}
              >
                <span className="profile-index">0{index + 1}</span>
                <div className="meta">
                  {isDemoProfile(profile) ? "Demo" : "Custom"}
                </div>
                <h2>{profileLabel(profile)}</h2>
                <p>
                  {(profile.explicit_preferences || []).join(" · ") ||
                    "A distinct cultural point of view."}
                </p>
                <div className="tags">
                  {tastes.map((taste) => (
                    <span className="tag" key={taste}>
                      {taste}
                    </span>
                  ))}
                </div>
              </button>
            );
          })}
        </div>
      )}

      <section className="create-panel" aria-label="Create anonymous profile">
        <div className="field">
          <label htmlFor="new-name">Create anonymous profile</label>
          <input
            id="new-name"
            value={newName}
            onChange={(event) => setNewName(event.target.value)}
            placeholder="Nickname only — no email required"
            maxLength={120}
          />
        </div>
        <button
          className="button secondary"
          type="button"
          disabled={creating}
          onClick={() => void handleCreateProfile()}
        >
          {creating ? "Creating…" : "Add profile"}
        </button>
      </section>

      <div className="form-row form-row-4">
        <div className="field">
          <label htmlFor="location">Location</label>
          <input
            id="location"
            value={location}
            onChange={(event) => setLocation(event.target.value)}
            placeholder="e.g. New York"
          />
        </div>
        <div className="field">
          <label htmlFor="experience">Experience</label>
          <select
            id="experience"
            value={experience}
            onChange={(event) =>
              setExperience(
                event.target.value as (typeof EXPERIENCES)[number]["value"],
              )
            }
          >
            {EXPERIENCES.map((item) => (
              <option key={item.value} value={item.value}>
                {item.label}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor="budget">Budget</label>
          <select
            id="budget"
            value={budget}
            onChange={(event) =>
              setBudget(
                event.target.value as "any" | "casual" | "mid" | "upscale",
              )
            }
          >
            <option value="any">Any</option>
            <option value="casual">Casual</option>
            <option value="mid">Mid</option>
            <option value="upscale">Upscale</option>
          </select>
        </div>
        <button
          className="button"
          type="button"
          disabled={selected.length !== 3}
          onClick={continueToEditor}
        >
          Edit preferences {selected.length}/3{" "}
          <span aria-hidden="true">→</span>
        </button>
      </div>
    </main>
  );
}
