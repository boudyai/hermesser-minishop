import { writable, get } from "svelte/store";

export function createDevicesStore({ api, t, showToast }) {
  const state = writable({
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

  async function loadDevices(devicesEnabled, force = false) {
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
      state.update((s) => ({
        ...s,
        devicesData: response,
        devicesLoaded: true,
        devicesErrorCode: "",
      }));
    } catch (error) {
      state.update((s) => ({
        ...s,
        devicesStatus: error?.message || t("wa_devices_load_failed"),
        devicesIsError: true,
        devicesErrorCode: String(error?.error || ""),
        devicesLoaded: true,
      }));
    } finally {
      state.update((s) => ({ ...s, devicesBusy: false }));
    }
  }

  function openDeviceDisconnectDialog(device) {
    state.update((s) => ({ ...s, deviceToDisconnect: device, deviceConfirmOpen: true }));
  }

  function closeDeviceDisconnectDialog() {
    const s = get(state);
    if (s.deviceDisconnectBusy) return;
    state.update((s) => ({ ...s, deviceConfirmOpen: false, deviceToDisconnect: null }));
  }

  async function disconnectDevice(devicesEnabled) {
    const s = get(state);
    const token = String(s.deviceToDisconnect?.token || "").trim();
    if (!token || s.deviceDisconnectBusy) return;
    state.update((s) => ({ ...s, deviceDisconnectBusy: true }));
    try {
      const response = await api("/devices/disconnect", {
        method: "POST",
        body: JSON.stringify({ token }),
      });
      if (!response?.ok) throw response;
      showToast(t("wa_device_disconnected"));
      state.update((s) => ({
        ...s,
        deviceConfirmOpen: false,
        deviceToDisconnect: null,
        devicesLoaded: false,
      }));
      await loadDevices(devicesEnabled, true);
    } catch (error) {
      showToast(error?.message || t("wa_device_disconnect_failed"));
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
