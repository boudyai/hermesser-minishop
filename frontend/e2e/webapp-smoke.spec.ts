import { test, expect, type ConsoleMessage, type Page } from "@playwright/test";

// Deterministic mock-smoke for the Svelte webapp (docs-demo build, mockApi, no
// backend). This is the standing UI regression gate for the runes migration: it
// asserts boot → home, every bottom-nav switch (icon-only buttons located by
// their Russian aria-label), the tariff-change modal, the lazy-loaded admin
// panel, and zero console errors throughout the run.

const APP_URL = "/demo/runtime/app/";

const NAV_TABS = [
  { label: "Главная", urlPart: "/demo/runtime/home" },
  { label: "Бонусы", urlPart: "/demo/runtime/invite" },
  { label: "Устройства", urlPart: "/demo/runtime/devices" },
  { label: "Поддержка", urlPart: "/demo/runtime/support" },
  { label: "Настройки", urlPart: "/demo/runtime/settings" },
] as const;

// Environmental noise that is not an app regression (no real backend / Telegram
// SDK / network in the mock). Keep this list tight — it must not mask app bugs.
const IGNORED_ERROR_PATTERNS: RegExp[] = [/favicon/i, /telegram\.org/i];

function isIgnoredError(text: string): boolean {
  return IGNORED_ERROR_PATTERNS.some((re) => re.test(text));
}

function trackErrors(page: Page): string[] {
  const errors: string[] = [];
  page.on("console", (msg: ConsoleMessage) => {
    if (msg.type() === "error" && !isIgnoredError(msg.text())) {
      errors.push(`console.error: ${msg.text()}`);
    }
  });
  page.on("pageerror", (err: Error) => {
    if (!isIgnoredError(err.message)) errors.push(`pageerror: ${err.message}`);
  });
  return errors;
}

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

test("boot, nav switching, tariff modal, admin lazy-load — no console errors", async ({ page }) => {
  const errors = trackErrors(page);

  // 1. Boot → home renders.
  await page.goto(APP_URL);
  const nav = page.locator("nav.bottom-nav");
  await expect(nav).toBeVisible();
  await expect(page.getByRole("button", { name: "Сменить тариф" })).toBeVisible();

  // 2. Switch every bottom-nav tab; assert URL + active state react.
  for (const tab of NAV_TABS) {
    const button = nav.getByRole("button", { name: tab.label, exact: true });
    await button.click();
    await expect(page).toHaveURL(new RegExp(escapeRegExp(tab.urlPart)));
    await expect(button).toHaveClass(/active/);
  }

  // 3. Tariff-change modal opens and closes.
  await nav.getByRole("button", { name: "Главная", exact: true }).click();
  await page.getByRole("button", { name: "Сменить тариф" }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible();
  await dialog.locator(".dialog-head button").click();
  await expect(dialog).toBeHidden();

  // 4. Admin lazy-load lands on the stats dashboard with the admin chrome.
  await nav.getByRole("button", { name: "Админ-панель", exact: true }).click();
  await expect(page).toHaveURL(/\/demo\/runtime\/admin\/stats/);
  await expect(page.locator("aside.admin-sidebar")).toBeVisible();

  // 5. Zero console errors throughout.
  expect(errors).toEqual([]);
});
