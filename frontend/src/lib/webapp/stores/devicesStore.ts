import { writable, get } from "svelte/store";
import type { ApiClient, DevicesResponse, PostPayload } from "../publicApi";
import { unwrap } from "../publicApi";

type Translate = (key: string, params?: Record<string, unknown>, fallback?: string) => string;
type DeviceRecord = Record<string, unknown>;
type DevicesState = {
  devicesData: DevicesResponse | null;
  devicesLoaded: boolean;
  devicesBusy: boolean;
  devicesStatus: string;
  devicesIsError: boolean;
  devicesErrorCode: string;
  deviceConfirmOpen: boolean;
  deviceToDisconnect: DeviceRecord | null;
  deviceDisconnectBusy: boolean;
};

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" ? (value as Record<string, unknown>) : {};
}

function stringField(value: unknown): string {
  return typeof value === "string" ? value : "";
}

export function createDevicesStore({
  api,
  t,
  showToast,
}: {
  api: ApiClient["api"];
  t: Translate;
  showToast: (message: string) => void;
}) {
  const state = writable<DevicesState>({
    devicesData: null,
    devicesLoaded: false,
    devicesBusy: false,
    devicesStatus: "",
    devicesIsError: false,
    devicesErrorCode: "",
    deviceConfirmOpen: false,
    deviceToDisconnect: null,
    deviceDisconnectBusy: false,
  });

  async function loadDevices(devicesEnabled: boolean, force = false) {
    const s = get(state);
    if (!devicesEnabled || s.devicesBusy || (s.devicesLoaded && !force)) return;
    state.update((s) => ({
      ...s,
      devicesBusy: true,
      devicesStatus: "",
      devicesIsError: false,
      devicesErrorCode: "",
    }));
    try {
      const response = await api("/devices");
      if (!response?.ok) throw response;
      const payload = unwrap(response);
      state.update((s) => ({
        ...s,
        devicesData: payload,
        devicesLoaded: true,
        devicesErrorCode: "",
      }));
    } catch (error: unknown) {
      const errorRecord = asRecord(error);
      state.update((s) => ({
        ...s,
        devicesStatus: stringField(errorRecord.message) || t("wa_devices_load_failed"),
        devicesIsError: true,
        devicesErrorCode: String(errorRecord.error || ""),
        devicesLoaded: true,
      }));
    } finally {
      state.update((s) => ({ ...s, devicesBusy: false }));
    }
  }

  function openDeviceDisconnectDialog(device: DeviceRecord) {
    state.update((s) => ({ ...s, deviceToDisconnect: device, deviceConfirmOpen: true }));
  }

  function closeDeviceDisconnectDialog() {
    const s = get(state);
    if (s.deviceDisconnectBusy) return;
    state.update((s) => ({ ...s, deviceConfirmOpen: false, deviceToDisconnect: null }));
  }

  async function disconnectDevice(devicesEnabled: boolean) {
    const s = get(state);
    const token = String(s.deviceToDisconnect?.token || "").trim();
    if (!token || s.deviceDisconnectBusy) return;
    state.update((s) => ({ ...s, deviceDisconnectBusy: true }));
    try {
      const response = await api("/devices/disconnect", {
        method: "POST",
        body: JSON.stringify({ token } satisfies PostPayload<"/api/devices/disconnect">),
      });
      if (!response?.ok) throw response;
      unwrap(response);
      showToast(t("wa_device_disconnected"));
      state.update((s) => ({
        ...s,
        deviceConfirmOpen: false,
        deviceToDisconnect: null,
        devicesLoaded: false,
      }));
      await loadDevices(devicesEnabled, true);
    } catch (error: unknown) {
      showToast(stringField(asRecord(error).message) || t("wa_device_disconnect_failed"));
    } finally {
      state.update((s) => ({ ...s, deviceDisconnectBusy: false }));
    }
  }

  return {
    subscribe: state.subscribe,
    set: state.set,
    update: state.update,
    loadDevices,
    openDeviceDisconnectDialog,
    closeDeviceDisconnectDialog,
    disconnectDevice,
  };
}
