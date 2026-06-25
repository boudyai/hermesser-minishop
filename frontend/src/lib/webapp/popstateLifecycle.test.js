import { describe, expect, it, vi } from "vitest";

import { createPopstateLifecycle } from "./popstateLifecycle.js";
import { resetShellState, shellState } from "./shellState.svelte.ts";

const SHARE_TOKEN = "0123456789abcdef0123456789abcdef";

async function flushPromises() {
  await Promise.resolve();
  await Promise.resolve();
}

function createDeps(overrides = {}) {
  const state = {
    activeTab: "home",
    adminActiveSection: "stats",
    canUseInstallGuides: false,
    devicesEnabled: true,
    fallbackAdminSection: "stats",
    isAdmin: false,
    isDocsDemo: false,
    mode: "app",
    pathname: "/",
    routePrefix: "",
    screen: "home",
    search: "",
    supportEnabled: true,
    windowPathname: "/",
    ...overrides,
  };
  resetShellState({
    activeTab: state.activeTab,
    adminActiveSection: state.adminActiveSection,
    mode: state.mode,
    screen: state.screen,
  });
  const adminRuntime = {
    cancelAdminAssetsPrefetch: vi.fn(),
    ensureAdminBundle: vi.fn(() => Promise.resolve({})),
    ensureI18nScope: vi.fn(() => Promise.resolve({})),
  };
  const deps = {
    adminRuntime,
    boot: vi.fn(),
    canUseInstallGuides: () => state.canUseInstallGuides,
    currentSearchParams: () => new URLSearchParams(state.search),
    getDevicesEnabled: () => state.devicesEnabled,
    getFallbackAdminSection: () => state.fallbackAdminSection,
    getIsAdmin: () => state.isAdmin,
    getSupportEnabled: () => state.supportEnabled,
    getWindowPathname: () => state.windowPathname,
    isDocsDemo: state.isDocsDemo,
    loadDevices: vi.fn(),
    loadInstallGuides: vi.fn(),
    loadPublicInstall: vi.fn(),
    loadSupport: vi.fn(),
    routePathnameFromLocation: () => state.pathname,
    routePrefix: state.routePrefix,
    setPasswordLoginMode: vi.fn(),
    showAdminUnavailable: vi.fn(),
    startSupportPolling: vi.fn(),
    syncAppSectionPath: vi.fn(),
  };
  return {
    adminRuntime,
    deps,
    lifecycle: createPopstateLifecycle(deps),
    state,
  };
}

describe("createPopstateLifecycle", () => {
  it("loads public install routes before other popstate work", () => {
    const { deps, lifecycle } = createDeps({
      pathname: `/s/${SHARE_TOKEN}`,
      windowPathname: `/s/${SHARE_TOKEN}`,
    });

    expect(lifecycle.handlePopstate()).toEqual({
      kind: "publicInstall",
      shareToken: SHARE_TOKEN,
    });

    expect(deps.loadPublicInstall).toHaveBeenCalledWith(SHARE_TOKEN);
    expect(deps.boot).not.toHaveBeenCalled();
    expect(shellState.screen).toBe("home");
  });

  it("boots when leaving public install mode", () => {
    const { deps, lifecycle } = createDeps({
      mode: "publicInstall",
      pathname: "/settings",
      windowPathname: "/settings",
    });

    expect(lifecycle.handlePopstate()).toEqual({ kind: "boot" });

    expect(deps.boot).toHaveBeenCalledOnce();
    expect(deps.loadPublicInstall).not.toHaveBeenCalled();
  });

  it("syncs password login mode for login routes", () => {
    const { deps, lifecycle } = createDeps({
      mode: "login",
      pathname: "/login/password",
      windowPathname: "/login/password",
    });

    expect(lifecycle.handlePopstate()).toEqual({
      kind: "login",
      passwordLoginEnabled: true,
    });

    expect(deps.setPasswordLoginMode).toHaveBeenCalledWith(true, true);
    expect(shellState.screen).toBe("login");
  });

  it("loads admin shell dependencies for admin routes", () => {
    const { adminRuntime, lifecycle } = createDeps({
      isAdmin: true,
      pathname: "/admin/users/42",
      windowPathname: "/admin/users/42",
    });

    expect(lifecycle.handlePopstate()).toEqual({
      activeTab: "settings",
      adminSection: "users",
      kind: "admin",
      section: "admin",
    });

    expect(adminRuntime.cancelAdminAssetsPrefetch).toHaveBeenCalledOnce();
    expect(adminRuntime.ensureI18nScope).toHaveBeenCalledWith("admin");
    expect(adminRuntime.ensureAdminBundle).toHaveBeenCalledOnce();
    expect(shellState).toMatchObject({
      activeTab: "settings",
      adminActiveSection: "users",
      screen: "admin",
    });
  });

  it("falls back to settings when admin bundle loading fails on the same route", async () => {
    const { adminRuntime, deps, lifecycle } = createDeps({
      isAdmin: true,
      pathname: "/admin/payments",
      screen: "home",
      windowPathname: "/admin/payments",
    });
    adminRuntime.ensureAdminBundle.mockRejectedValueOnce(new Error("missing bundle"));

    lifecycle.handlePopstate();
    await flushPromises();

    expect(shellState.screen).toBe("settings");
    expect(deps.syncAppSectionPath).toHaveBeenCalledWith("settings", true);
    expect(deps.showAdminUnavailable).toHaveBeenCalledOnce();
  });

  it("loads only the selected section data", () => {
    const support = createDeps({
      pathname: "/support",
      supportEnabled: true,
      windowPathname: "/support",
    });
    expect(support.lifecycle.handlePopstate()).toMatchObject({
      kind: "section",
      loadSupport: true,
      section: "support",
    });
    expect(support.deps.loadSupport).toHaveBeenCalledOnce();
    expect(support.deps.startSupportPolling).toHaveBeenCalledOnce();
    expect(support.deps.loadDevices).not.toHaveBeenCalled();
    expect(support.deps.loadInstallGuides).not.toHaveBeenCalled();

    const install = createDeps({
      canUseInstallGuides: true,
      pathname: "/install",
      windowPathname: "/install",
    });
    install.lifecycle.handlePopstate();
    expect(install.deps.loadInstallGuides).toHaveBeenCalledOnce();
    expect(install.deps.loadSupport).not.toHaveBeenCalled();
  });
});
