import { expect, test } from "@playwright/test";

test("group concierge journey with edit, compare, reject", async ({ page }) => {
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: /Cultural Intelligence Layer/i }),
  ).toBeVisible();
  await expect(page.getByText(/Demo mode|Live mode|API offline/i).first()).toBeVisible();

  await page.getByRole("link", { name: /Plan for a group/i }).click();
  await expect(
    page.getByRole("heading", { name: /Who are we planning for/i }),
  ).toBeVisible();

  const cards = page.locator(".profile-card");
  await expect(cards).toHaveCount(3, { timeout: 20_000 });
  await cards.nth(0).click();
  await cards.nth(1).click();
  await cards.nth(2).click();
  await page.getByRole("button", { name: /Edit preferences 3\/3/i }).click();

  await expect(
    page.getByRole("heading", { name: /Edit cultural preferences/i }),
  ).toBeVisible();
  await page.getByRole("button", { name: /Compare tastes/i }).click();

  await expect(
    page.getByRole("heading", { name: /Group taste comparison/i }),
  ).toBeVisible();
  await expect(page.getByText(/Where tastes meet/i)).toBeVisible();
  await expect(page.getByText(/tasteos_local_token_overlap_v1/i)).toBeVisible();

  await page.getByRole("button", { name: /Build the group plan/i }).click();

  await expect(
    page.getByRole("heading", { name: /Recommendations & itinerary/i }),
  ).toBeVisible({ timeout: 45_000 });
  await expect(page.getByText(/demo mode/i).first()).toBeVisible();
  await expect(page.getByText(/proposed plan only|does not confirm reservations/i).first()).toBeVisible();

  const primary = page.locator(".result-card.primary h2");
  await expect(primary).toBeVisible();
  const primaryName = await primary.innerText();
  await page.getByRole("button", { name: /Reject & regenerate/i }).click();
  await expect(primary).not.toHaveText(primaryName, { timeout: 45_000 });
  await expect(page.getByText(/Per-person evidence/i)).toBeVisible();
  await expect(page.getByText(/Proposed itinerary/i)).toBeVisible();
});

test("create anonymous profile validation", async ({ page }) => {
  await page.goto("/concierge");
  await page.getByRole("button", { name: /Add profile/i }).click();
  await expect(
    page.getByText(/Enter a nickname for the new anonymous profile/i),
  ).toBeVisible();

  await page.locator("#new-name").fill("Riley");
  await page.getByRole("button", { name: /Add profile/i }).click();
  await expect(
    page.getByRole("button", { name: /Select Riley|Deselect Riley/i }),
  ).toBeVisible({ timeout: 20_000 });
});

test("developers page lists API contracts", async ({ page }) => {
  await page.goto("/developers");
  await expect(
    page.getByRole("heading", { name: /Culture, as infrastructure/i }),
  ).toBeVisible();
  await expect(page.getByText("/api/v1/concierge/plan", { exact: true })).toBeVisible();
  await expect(page.getByRole("link", { name: /Open API docs/i })).toBeVisible();
});
