export const API_BASE_URL =
  (process.env.NEXT_PUBLIC_API_BASE_URL || "").trim() || "http://localhost:8000";

export type ApiMode = {
  mode: "demo" | "live" | string;
  label: string;
  description: string;
  qloo_key_configured: boolean;
};

export type Favorite = {
  entity_id: string;
  name: string;
  entity_type: string;
  image_url?: string | null;
  description?: string | null;
};

export type Profile = {
  id: string;
  display_name: string;
  favorites: Favorite[];
  preferred_domains: string[];
  exclusions: string[];
  explicit_preferences: string[];
  notes?: string | null;
  is_demo?: boolean;
  created_at?: string;
  updated_at?: string;
};

export type ProfileCreate = {
  display_name: string;
  favorites?: Favorite[];
  preferred_domains?: string[];
  exclusions?: string[];
  explicit_preferences?: string[];
  notes?: string | null;
};

export type ProfileUpdate = Partial<ProfileCreate>;

export type ParticipantMatch = {
  profile_id: string;
  display_name: string;
  status: "supported" | "unknown" | "conflict" | "excluded" | string;
  evidence: string[];
  app_score: number | null;
  qloo_affinity: number | null;
  notes: string;
};

export type PipelineStage = {
  stage?: string;
  status?: string;
  method?: string;
  note?: string;
  [key: string]: unknown;
};

export type Candidate = {
  entity_id: string;
  name: string;
  category?: string;
  description?: string | null;
  image_url?: string | null;
  source?: string;
  qloo_affinity?: number | null;
  app_rank_score?: number;
  participant_matches?: ParticipantMatch[];
  evidence_refs?: string[];
  match_explanation?: string;
  limitations?: string[];
  ranking_inputs?: Record<string, unknown>;
};

export type PlanStop = {
  order: number;
  kind: string;
  title: string;
  detail: string;
  candidate?: Candidate | null;
  is_proposed?: boolean;
};

export type ConciergePlan = {
  id: string;
  mode: string;
  experience?: string;
  primary: Candidate;
  alternatives: Candidate[];
  itinerary: PlanStop[];
  tradeoffs: string;
  selection_rationale?: string;
  disclaimer?: string;
  reconciliation: ParticipantMatch[];
  pipeline: PipelineStage[];
  limitations: string[];
  rejected_entity_ids?: string[];
};

export type PlanRequest = {
  profile_ids: string[];
  target_domain: "urn:entity:place";
  location_query?: string;
  experience?: "evening_out" | "dinner" | "drinks" | "culture_night";
  budget?: "any" | "casual" | "mid" | "upscale";
  exclusions?: string[];
  take: number;
  alternatives_count?: number;
  rejected_entity_ids?: string[];
};

export class ApiError extends Error {
  constructor(
    message: string,
    public status?: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

function messageFromBody(raw: string, status: number): string {
  if (!raw) return `API request failed with status ${status}.`;
  try {
    const parsed = JSON.parse(raw) as {
      error?: { message?: string };
      detail?: string;
    };
    if (parsed.error?.message) return parsed.error.message;
    if (typeof parsed.detail === "string") return parsed.detail;
  } catch {
    /* plain text */
  }
  return raw.slice(0, 400);
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...init?.headers,
      },
    });
  } catch {
    throw new ApiError(
      `TasteOS API is unreachable at ${API_BASE_URL}. Start the API or update NEXT_PUBLIC_API_BASE_URL.`,
    );
  }

  if (!response.ok) {
    const detail = await response.text().catch(() => "");
    throw new ApiError(messageFromBody(detail, response.status), response.status);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}

export function profileLabel(profile: Profile): string {
  return profile.display_name || String(profile.id);
}

export function profileTasteTags(profile: Profile): string[] {
  const fromFavorites = (profile.favorites || []).map((f) => f.name);
  const fromPrefs = profile.explicit_preferences || [];
  return [...fromFavorites, ...fromPrefs].slice(0, 8);
}

export function isDemoProfile(profile: Profile): boolean {
  return Boolean(profile.is_demo || profile.id.startsWith("demo-"));
}

export const getMode = () => request<ApiMode>("/api/v1/mode");
export const getDemoProfiles = () => request<Profile[]>("/api/v1/profiles/demo");
export const getProfile = (id: string) =>
  request<Profile>(`/api/v1/profiles/${encodeURIComponent(id)}`);
export const createProfile = (body: ProfileCreate) =>
  request<Profile>("/api/v1/profiles", {
    method: "POST",
    body: JSON.stringify(body),
  });
export const updateProfile = (id: string, body: ProfileUpdate) =>
  request<Profile>(`/api/v1/profiles/${encodeURIComponent(id)}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
export const deleteProfile = (id: string) =>
  request<void>(`/api/v1/profiles/${encodeURIComponent(id)}`, {
    method: "DELETE",
  });
export const createPlan = (body: PlanRequest) =>
  request<ConciergePlan>("/api/v1/concierge/plan", {
    method: "POST",
    body: JSON.stringify(body),
  });
export const rejectCandidate = (planId: string, entityId: string) =>
  request<ConciergePlan>(
    `/api/v1/concierge/plan/${encodeURIComponent(planId)}/reject?entity_id=${encodeURIComponent(entityId)}`,
    { method: "POST" },
  );
