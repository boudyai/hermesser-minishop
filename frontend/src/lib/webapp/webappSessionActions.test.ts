import { describe, expect, it, vi } from "vitest";

import { createWebappSessionActions } from "./webappSessionActions.js";
import { resetShellState, shellState } from "./shellState.svelte";
type TestOverrides = { [key: string]: Record<string, unknown> | undefined };

function makeActions(overrides: TestOverrides = {}) {
  resetShellState();
  const storage = {
    clearManualLogoutFlag: vi.fn(),
    clearStoredToken: vi.fn(),
    isManuallyLoggedOut: vi.fn(() => false),
    markManualLogout: vi.fn(),
    readCookie: vi.fn(() => "cookie-csrf"),
  };
  const deps = {
    csrfCookieName: "csrf",
    isMock: () => false,
    manualLogoutFlagKey: "manual",
    storage,
    ...overrides.deps,
  };
  return {
    actions: createWebappSessionActions(deps),
    deps,
    storage,
  };
}

describe("createWebappSessionActions", () => {
  it("sets token state and reads csrf from the cookie fallback", () => {
    const { actions, storage } = makeActions();

    actions.setToken("jwt");

    expect(shellState).toMatchObject({ csrfToken: "cookie-csrf", token: "jwt" });
    expect(storage.clearManualLogoutFlag).toHaveBeenCalledWith("manual");
    expect(storage.readCookie).toHaveBeenCalledWith("csrf");
    expect(storage.clearStoredToken).toHaveBeenCalledOnce();
  });

  it("uses the explicit csrf token and keeps stored token in mock mode", () => {
    const { actions, storage } = makeActions({
      deps: { isMock: () => true },
    });

    actions.setToken("jwt", "explicit-csrf");

    expect(shellState).toMatchObject({ csrfToken: "explicit-csrf", token: "jwt" });
    expect(storage.readCookie).not.toHaveBeenCalled();
    expect(storage.clearStoredToken).not.toHaveBeenCalled();
  });

  it("clears token state and persisted token", () => {
    const { actions, storage } = makeActions();
    shellState.csrfToken = "csrf";
    shellState.token = "jwt";

    actions.clearToken();

    expect(shellState).toMatchObject({ csrfToken: "", token: "" });
    expect(storage.clearStoredToken).toHaveBeenCalledOnce();
  });

  it("delegates manual logout operations to storage", () => {
    const { actions, storage } = makeActions();
    storage.isManuallyLoggedOut.mockReturnValue(true);

    actions.markManualLogout();
    actions.clearManualLogoutFlag();

    expect(actions.isManuallyLoggedOut()).toBe(true);
    expect(storage.markManualLogout).toHaveBeenCalledWith("manual");
    expect(storage.clearManualLogoutFlag).toHaveBeenCalledWith("manual");
    expect(storage.isManuallyLoggedOut).toHaveBeenCalledWith("manual");
  });
});
