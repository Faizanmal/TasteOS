import type { Profile } from "@/lib/api";
import { profileTasteTags } from "@/lib/api";

export type OverlapReport = {
  shared: string[];
  uniqueByProfile: { id: string; name: string; unique: string[] }[];
  exclusionHits: string[];
  /** Local calculation label for UI honesty */
  method: "tasteos_local_token_overlap_v1";
};

/** Compute taste-token overlap from user-provided / demo profile fields only. */
export function computeTasteOverlap(profiles: Profile[]): OverlapReport {
  const bags = profiles.map((p) => ({
    id: p.id,
    name: p.display_name,
    tokens: new Set(
      profileTasteTags(p).map((t) => t.trim().toLowerCase()).filter(Boolean),
    ),
  }));

  let shared: string[] = [];
  if (bags.length > 0) {
    const [first, ...rest] = bags;
    shared = [...first.tokens].filter((token) =>
      rest.every((bag) => bag.tokens.has(token)),
    );
  }

  const uniqueByProfile = bags.map((bag) => ({
    id: bag.id,
    name: bag.name,
    unique: [...bag.tokens].filter(
      (token) => !bags.some((other) => other.id !== bag.id && other.tokens.has(token)),
    ),
  }));

  const exclusionHits = [
    ...new Set(profiles.flatMap((p) => p.exclusions || [])),
  ];

  return {
    shared: shared.map(titleCase),
    uniqueByProfile: uniqueByProfile.map((row) => ({
      ...row,
      unique: row.unique.map(titleCase),
    })),
    exclusionHits,
    method: "tasteos_local_token_overlap_v1",
  };
}

function titleCase(value: string): string {
  return value.replace(/\b\w/g, (c) => c.toUpperCase());
}
