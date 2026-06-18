import { writable } from "svelte/store";
import { adminErrorMessage } from "../errors.js";

export function createStatsStore({ api, onToast, at }) {
  const state = writable({
    stats: null,
    statsLoading: false,
    statsError: "",
    syncBusy: false,
  });

  async function loadStats() {
    state.update((s) => ({ ...s, statsLoading: true, statsError: "" }));
    try {
      const data = await api("/admin/stats");
      if (!data?.ok) {
        state.update((s) => ({ ...s, statsError: adminErrorMessage(data, at, "load_failed") }));
      } else {
        state.update((s) => ({ ...s, stats: data }));
      }
    } catch (e) {
      state.update((s) => ({ ...s, statsError: e?.message || String(e) }));
    } finally {
      state.update((s) => ({ ...s, statsLoading: false }));
    }
  }

  async function triggerSync() {
    let busy = false;
    state.update((s) => {
      busy = s.syncBusy;
      return s;
    });
    if (busy) return;

    state.update((s) => ({ ...s, syncBusy: true }));
    try {
      const res = await api("/admin/sync", { method: "POST" });
      if (res?.ok) {
        onToast(at("sync_started", {}, "Синхронизация запущена"));
        await loadStats();
      } else {
        onToast(adminErrorMessage(res, at, at("sync_error", {}, "Ошибка синхронизации")));
      }
    } finally {
      state.update((s) => ({ ...s, syncBusy: false }));
    }
  }

  return {
    subscribe: state.subscribe,
    set: state.set,
    update: state.update,
    loadStats,
    triggerSync,
  };
}
