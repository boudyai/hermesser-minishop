import { afterEach, describe, expect, it, vi } from "vitest";

import { runWebappBoot } from "./webappBoot.js";

function installBrowser(search = "") {
  vi.stubGlobal("document", { title: "Mini Shop" });
  vi.stubGlobal("window", {
    location: {
      href: `https://app.example.com/${search}`,
      search,
    },
    history: { replaceState: vi.fn() },
  });
}

function makeDeps(overrides = {}) {
  return {
    MOCK: false,
    setMode: vi.fn(),
    hasTelegramLaunchParams: vi.fn(() => false),
    loadTelegramSdk: vi.fn(),
    prepareTelegramMiniApp: vi.fn(),
    loadData: vi.fn(),
    showLogin: vi.fn(),
    clearToken: vi.fn(),
    clearManualLogoutFlag: vi.fn(),
    isManuallyLoggedOut: vi.fn(() => false),
    hasEmailCodeLoginDeeplink: vi.fn(() => false),
    finalizeMagicLogin: vi.fn(),
    finalizeTelegramAuth: vi.fn(),
    setAuthStatus: vi.fn(),
    t: (key) => key,
    getInitDataForBoot: vi.fn(() => ""),
    getToken: vi.fn(() => ""),
    getCsrfToken: vi.fn(() => ""),
    ...overrides,
  };
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("runWebappBoot", () => {
  it("maps invite-required Telegram OAuth status to the dedicated auth copy", async () => {
    installBrowser("?telegram_auth=invite_required");
    const deps = makeDeps();

    await runWebappBoot(deps);

    expect(deps.setAuthStatus).toHaveBeenCalledWith("wa_auth_invite_required", true);
    expect(deps.showLogin).toHaveBeenCalledOnce();
    expect(window.history.replaceState).toHaveBeenCalledOnce();
  });
});
