import { describe, expect, it, vi } from "vitest";

import { createTelegramRuntime } from "./telegramRuntime.js";
import { resetShellState, shellState } from "./shellState.svelte";

type FakeTelegram = { platform: string } | null;

function makeRuntime({
  initData = "initial-init",
  telegram = { platform: "ios" } as FakeTelegram,
} = {}) {
  resetShellState();
  const state: { initData: string; telegram: FakeTelegram } = {
    initData,
    telegram,
  };
  const sdk = {
    get initData() {
      return state.initData;
    },
    hasLaunchParams: vi.fn(() => true),
    load: vi.fn(async () => {
      state.telegram = { platform: "android" };
      state.initData = "loaded-init";
      return state.telegram;
    }),
    readInitDataFromLocation: vi.fn(() => "location-init"),
    refresh: vi.fn(() => {
      return state.telegram;
    }),
  };
  const createSdk = vi.fn(() => sdk);
  const runtime = createTelegramRuntime({
    actionTimeoutMs: 20,
    bootTimeoutMs: 10,
    createSdk,
    miniAppAuthTimeoutMs: 30,
    scriptUrl: "https://telegram.example/sdk.js",
  } as unknown as Parameters<typeof createTelegramRuntime>[0]);
  return { createSdk, runtime, sdk, state };
}

describe("createTelegramRuntime", () => {
  it("creates the sdk and applies the initial refresh state", () => {
    const { createSdk, sdk, state } = makeRuntime();

    expect(createSdk).toHaveBeenCalledWith({
      actionTimeoutMs: 20,
      bootTimeoutMs: 10,
      miniAppAuthTimeoutMs: 30,
      onInitDataChange: expect.any(Function),
      onStatusChange: expect.any(Function),
      scriptUrl: "https://telegram.example/sdk.js",
    });
    expect(sdk.refresh).toHaveBeenCalledOnce();
    expect(shellState.tg).toBe(state.telegram);
    expect(shellState.telegramSdkStatus).toBe("ready");
    expect(shellState.telegramMiniAppInitData).toBe("initial-init");
  });

  it("keeps status idle when the initial refresh has no web app", () => {
    makeRuntime({ initData: "", telegram: null });

    expect(shellState.tg).toBeNull();
    expect(shellState.telegramSdkStatus).toBe("idle");
    expect(shellState.telegramMiniAppInitData).toBe("");
  });

  it("updates telegram and init data after launch loading", async () => {
    const { runtime, state } = makeRuntime();

    const loadedTelegram = await runtime.load();

    expect(loadedTelegram).toBe(state.telegram);
    expect(shellState.tg).toEqual({ platform: "android" });
    expect(shellState.telegramMiniAppInitData).toBe("loaded-init");
  });

  it("proxies launch parameter and location init-data helpers", () => {
    const { runtime, sdk } = makeRuntime();

    expect(runtime.hasLaunchParams()).toBe(true);
    expect(runtime.readInitDataFromLocation()).toBe("location-init");
    expect(sdk.hasLaunchParams).toHaveBeenCalledOnce();
    expect(sdk.readInitDataFromLocation).toHaveBeenCalledOnce();
  });

  it("refreshes the shell-owned telegram binding", () => {
    const { runtime, state } = makeRuntime();
    state.telegram = { platform: "desktop" };
    state.initData = "refreshed-init";

    expect(runtime.refreshTelegram()).toEqual({ platform: "desktop" });

    expect(shellState.tg).toEqual({ platform: "desktop" });
    expect(shellState.telegramSdkStatus).toBe("ready");
    expect(shellState.telegramMiniAppInitData).toBe("refreshed-init");
  });

  it("does not overwrite status on later empty refreshes", () => {
    const { runtime, state } = makeRuntime();
    state.telegram = null;
    shellState.telegramSdkStatus = "ready";

    expect(runtime.refreshTelegram()).toBeNull();

    expect(shellState.tg).toBeNull();
    expect(shellState.telegramSdkStatus).toBe("ready");
  });
});
