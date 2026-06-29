import { test, expect, type ConsoleMessage, type Page } from "@playwright/test";

// Deterministic mock-smoke for the Svelte webapp (docs-demo build, mockApi, no
// backend). This is the standing UI regression gate for the runes migration: it
// asserts boot → home, every bottom-nav switch (icon-only buttons located by
// their Russian aria-label), the tariff-change modal, admin lazy-load, the
// tariffs editor path, and zero console errors / selected Svelte warnings
// throughout the run.

const APP_URL = "/demo/runtime/app/";

const NAV_TABS = [
  { label: "Главная", urlPart: "/demo/runtime/home" },
  { label: "Бонусы", urlPart: "/demo/runtime/invite" },
  { label: "Устройства", urlPart: "/demo/runtime/devices" },
  { label: "Поддержка", urlPart: "/demo/runtime/support" },
  { label: "Настройки", urlPart: "/demo/runtime/settings" },
] as const;

const REQUIRED_ADMIN_SECTIONS = ["Дашборд", "Тарифы"] as const;

// Environmental noise that is not an app regression (no real backend / Telegram
// SDK / network in the mock). Keep this list tight — it must not mask app bugs.
const IGNORED_ERROR_PATTERNS: RegExp[] = [/favicon/i, /telegram\.org/i];

function isIgnoredError(text: string): boolean {
  return IGNORED_ERROR_PATTERNS.some((re) => re.test(text));
}

function trackErrors(page: Page, phase: () => string): string[] {
  const errors: string[] = [];
  page.on("console", (msg: ConsoleMessage) => {
    const location = msg.location();
    const where = location.url ? ` at ${location.url}:${location.lineNumber}` : "";
    if (msg.type() === "error" && !isIgnoredError(msg.text())) {
      errors.push(`[${phase()}] console.error${where}: ${msg.text()}`);
    }
    if (msg.type() === "warning" && /derived_inert/.test(msg.text())) {
      errors.push(`[${phase()}] console.warning${where}: ${msg.text()}`);
    }
  });
  page.on("pageerror", (err: Error) => {
    if (!isIgnoredError(err.message)) errors.push(`[${phase()}] pageerror: ${err.message}`);
  });
  return errors;
}

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

test("boot, nav switching, tariff modal, admin tariff editor — no console errors", async ({
  page,
}) => {
  let phase = "boot";
  const errors = trackErrors(page, () => phase);

  // 1. Boot → home renders.
  phase = "boot";
  await page.goto(APP_URL);
  const nav = page.locator("nav.bottom-nav");
  await expect(nav).toBeVisible();
  await expect(page.getByRole("button", { name: "Сменить тариф" })).toBeVisible();

  // 2. Switch every bottom-nav tab; assert URL + active state react.
  phase = "bottom-nav";
  for (const tab of NAV_TABS) {
    const button = nav.getByRole("button", { name: tab.label, exact: true });
    await button.click();
    await expect(page).toHaveURL(new RegExp(escapeRegExp(tab.urlPart)));
    await expect(button).toHaveClass(/active/);
  }

  // 3. Tariff-change modal opens and closes.
  phase = "webapp-tariff-modal";
  await nav.getByRole("button", { name: "Главная", exact: true }).click();
  await page.getByRole("button", { name: "Сменить тариф" }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible();
  await dialog.locator(".dialog-head button").click();
  await expect(dialog).toBeHidden();

  // 4. Admin lazy-load lands on the stats dashboard with the admin chrome.
  phase = "admin-stats";
  await nav.getByRole("button", { name: "Админ-панель", exact: true }).click();
  await expect(page).toHaveURL(/\/demo\/runtime\/admin\/stats/);
  const adminSidebar = page.locator("aside.admin-sidebar");
  await expect(adminSidebar).toBeVisible();
  for (const sectionName of REQUIRED_ADMIN_SECTIONS) {
    await expect(
      adminSidebar.getByRole("button", { name: sectionName, exact: true })
    ).toBeVisible();
  }

  // 5. Every visible admin section can be visited without console regressions.
  const adminSectionButtons = adminSidebar.locator(".admin-nav-item");
  const adminSectionCount = await adminSectionButtons.count();
  for (let index = 0; index < adminSectionCount; index += 1) {
    const sectionButton = adminSectionButtons.nth(index);
    const sectionName = (await sectionButton.textContent())?.trim() || `#${index + 1}`;
    phase = `admin-section:${sectionName}`;
    await sectionButton.click();
    await expect(page.locator(".admin-section-stage:not([inert])")).toBeVisible();
  }

  // 6. The tariffs section opens the editor from a catalog card.
  phase = "admin-tariffs-nav";
  await page.getByRole("button", { name: "Тарифы", exact: true }).click();
  await expect(page).toHaveURL(/\/demo\/runtime\/admin\/tariffs/);
  await expect(page.getByRole("heading", { name: "Каталог тарифов" })).toBeVisible();
  phase = "admin-tariffs-configure";
  await page.getByRole("button", { name: "Настроить" }).first().click();
  await expect(page.getByRole("dialog").filter({ hasText: "Ключ тарифа" })).toBeVisible();

  // 7. Zero console errors and no Svelte derived-lifecycle warnings throughout.
  expect(errors).toEqual([]);
});
