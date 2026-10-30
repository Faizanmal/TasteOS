import { expect, test } from "@playwright/test";
import { computeTasteOverlap } from "../../src/lib/overlap";
import type { Profile } from "../../src/lib/api";

const base = (id: string, name: string, favs: string[], prefs: string[]): Profile => ({
  id,
  display_name: name,
  favorites: favs.map((n, i) => ({
    entity_id: `${id}-f${i}`,
    name: n,
    entity_type: "urn:entity:place",
  })),
  preferred_domains: ["urn:entity:place"],
  exclusions: id === "a" ? ["demo-place-x"] : [],
  explicit_preferences: prefs,
});

test("overlap reports shared and unique tokens", () => {
  const report = computeTasteOverlap([
    base("a", "A", ["Radiohead", "The Bear"], ["comfort food"]),
    base("b", "B", ["Radiohead", "Beyoncé"], ["lively"]),
    base("c", "C", ["Radiohead", "Patagonia"], ["comfort food"]),
  ]);
  expect(report.method).toBe("tasteos_local_token_overlap_v1");
  expect(report.shared.map((s) => s.toLowerCase())).toContain("radiohead");
  expect(report.exclusionHits).toContain("demo-place-x");
  const aUnique = report.uniqueByProfile.find((r) => r.id === "a");
  expect(aUnique?.unique.map((s) => s.toLowerCase())).toEqual(
    expect.arrayContaining(["the bear"]),
  );
});
