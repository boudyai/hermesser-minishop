import { describe, expect, it, vi } from "vitest";

import { createDevicesStore } from "./devicesStore.ts";

function makeDevicesStore(api = vi.fn()) {
  const deps = {
    api,
    t: (key) => key,
    showToast: vi.fn(),
  };
  return { store: createDevicesStore(deps), deps };
}

describe("devicesStore", () => {
  it("refreshes the devices payload after a successful disconnect", async () => {
    const api = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        current_devices: 1,
        max_devices: 3,
        devices: [{ token: "device-token", display_name: "Phone" }],
      })
      .mockResolvedValueOnce({ ok: true })
      .mockResolvedValueOnce({
        ok: true,
        current_devices: 0,
        max_devices: 3,
        devices: [],
      });
    const { store, deps } = makeDevicesStore(api);

    await store.loadDevices(true);
    store.openDeviceDisconnectDialog({ token: "device-token", display_name: "Phone" });
    await store.disconnectDevice(true);

    expect(api).toHaveBeenNthCalledWith(1, "/devices");
    expect(api).toHaveBeenNthCalledWith(2, "/devices/disconnect", {
      method: "POST",
      body: JSON.stringify({ token: "device-token" }),
    });
    expect(api).toHaveBeenNthCalledWith(3, "/devices");
    expect(store.devicesData).toMatchObject({ current_devices: 0, devices: [] });
    expect(store.deviceConfirmOpen).toBe(false);
    expect(store.deviceToDisconnect).toBe(null);
    expect(deps.showToast).toHaveBeenCalledWith("wa_device_disconnected");
  });
});
