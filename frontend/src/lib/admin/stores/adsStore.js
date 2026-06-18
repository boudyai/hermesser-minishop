import { writable } from "svelte/store";
import { adminErrorMessage } from "../errors.js";

export function createAdsStore({ api, onToast, at }) {
  const state = writable({
    ads: [],
    adsTotals: null,
    adsLoading: false,
    adCreateOpen: false,
    adDraft: { source: "", start_param: "", cost: 0 },
  });

  async function loadAds() {
    state.update((s) => ({ ...s, adsLoading: true }));
    try {
      const data = await api("/admin/ads");
      if (data?.ok) {
        state.update((s) => ({
          ...s,
          ads: data.campaigns || [],
          adsTotals: data.totals || {},
        }));
      }
    } finally {
      state.update((s) => ({ ...s, adsLoading: false }));
    }
  }

  async function createAd() {
    let draft = null;
    state.update((s) => {
      draft = s.adDraft;
      return s;
    });
    if (!draft.source.trim() || !draft.start_param.trim()) return;

    const res = await api("/admin/ads", {
      method: "POST",
      body: JSON.stringify(draft),
    });

    if (res?.ok) {
      onToast(at("ad_created", {}, "Кампания создана"));
      state.update((s) => ({
        ...s,
        adCreateOpen: false,
        adDraft: { source: "", start_param: "", cost: 0 },
      }));
      await loadAds();
    } else {
      onToast(adminErrorMessage(res, at));
    }
  }

  async function toggleAd(ad) {
    const res = await api(`/admin/ads/${ad.id}/toggle`, {
      method: "POST",
      body: JSON.stringify({ is_active: !ad.is_active }),
    });
    if (res?.ok) {
      state.update((s) => ({
        ...s,
        ads: s.ads.map((c) => (c.id === ad.id ? { ...c, is_active: !ad.is_active } : c)),
      }));
    } else {
      onToast(adminErrorMessage(res, at));
    }
  }

  async function deleteAd(ad) {
    const res = await api(`/admin/ads/${ad.id}`, { method: "DELETE" });
    if (res?.ok) {
      state.update((s) => ({
        ...s,
        ads: s.ads.filter((c) => c.id !== ad.id),
      }));
      onToast(at("ad_deleted", {}, "Кампания удалена"));
    } else {
      onToast(adminErrorMessage(res, at));
    }
  }

  function setCreateOpen(open) {
    state.update((s) => ({ ...s, adCreateOpen: open }));
  }

  function updateDraft(fields) {
    state.update((s) => ({ ...s, adDraft: { ...s.adDraft, ...fields } }));
  }

  return {
    subscribe: state.subscribe,
    set: state.set,
    update: state.update,
    loadAds,
    createAd,
    toggleAd,
    deleteAd,
    setCreateOpen,
    updateDraft,
  };
}
