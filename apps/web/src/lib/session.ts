import type { Profile } from "@/lib/api";

const PROFILES_KEY = "tasteos_profiles";
const CONSTRAINTS_KEY = "tasteos_constraints";
const PLAN_KEY = "tasteos_plan";

export type Constraints = {
  location: string;
  experience: "evening_out" | "dinner" | "drinks" | "culture_night";
  budget: "any" | "casual" | "mid" | "upscale";
};

export const DEFAULT_CONSTRAINTS: Constraints = {
  location: "New York",
  experience: "evening_out",
  budget: "any",
};

function safeParse<T>(raw: string | null, fallback: T): T {
  if (!raw) return fallback;
  try {
    return JSON.parse(raw) as T;
  } catch {
    return fallback;
  }
}

export function readProfiles(): Profile[] {
  if (typeof window === "undefined") return [];
  return safeParse<Profile[]>(localStorage.getItem(PROFILES_KEY), []);
}

export function writeProfiles(profiles: Profile[]) {
  localStorage.setItem(PROFILES_KEY, JSON.stringify(profiles));
}

export function readConstraints(): Constraints {
  if (typeof window === "undefined") return DEFAULT_CONSTRAINTS;
  return {
    ...DEFAULT_CONSTRAINTS,
    ...safeParse<Partial<Constraints>>(
      localStorage.getItem(CONSTRAINTS_KEY),
      {},
    ),
  };
}

export function writeConstraints(constraints: Constraints) {
  localStorage.setItem(CONSTRAINTS_KEY, JSON.stringify(constraints));
}

export function clearPlanCache() {
  sessionStorage.removeItem(PLAN_KEY);
}

export function readPlanCache<T>(): T | null {
  if (typeof window === "undefined") return null;
  const raw = sessionStorage.getItem(PLAN_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as T;
  } catch {
    sessionStorage.removeItem(PLAN_KEY);
    return null;
  }
}

export function writePlanCache(plan: unknown) {
  sessionStorage.setItem(PLAN_KEY, JSON.stringify(plan));
}
