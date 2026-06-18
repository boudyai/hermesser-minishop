import { writable } from "svelte/store";
import { adminErrorMessage } from "../errors.js";

export function createPromosStore({
  api,
  onToast,
  at = (key, _params, fallback) => fallback || key,
}) {
  const state = writable({
    promos: [],
    promosTotal: 0,
    promosPage: 0,
    promosLoading: false,
    promoCreateOpen: false,
    promoDraft: { code: "", bonus_days: 7, max_activations: 1, valid_days: 30 },
  });

  const PROMOS_PAGE_SIZE = 25;

  async function loadPromos() {
    state.update((s) => ({ ...s, promosLoading: true }));
    let currentPage = 0;
    state.update((s) => {
      currentPage = s.promosPage;
      return s;
    });
    try {
      const data = await api(`/admin/promos?page=${currentPage}&page_size=${PROMOS_PAGE_SIZE}`);
      if (data?.ok) {
        state.update((s) => ({ ...s, promos: data.promos || [], promosTotal: data.total || 0 }));
      }
    } finally {
      state.update((s) => ({ ...s, promosLoading: false }));
    }
  }

  async function createPromo() {
    let draft = null;
    state.update((s) => {
      draft = s.promoDraft;
      return s;
    });
    if (!draft.code.trim()) return;

    const res = await api("/admin/promos", {
      method: "POST",
      body: JSON.stringify(draft),
    });

    if (res?.ok) {
      onToast("Промокод создан");
      state.update((s) => ({
        ...s,
        promoCreateOpen: false,
        promoDraft: { code: "", bonus_days: 7, max_activations: 1, valid_days: 30 },
      }));
      await loadPromos();
    } else {
      onToast(adminErrorMessage(res, at, "Ошибка"));
    }
  }

  async function togglePromo(promo) {
    const res = await api(`/admin/promos/${promo.id}`, {
      method: "PATCH",
      body: JSON.stringify({ is_active: !promo.is_active }),
    });
    if (res?.ok) {
      state.update((s) => ({
        ...s,
        promos: s.promos.map((p) => (p.id === promo.id ? res.promo : p)),
      }));
    } else {
      onToast(adminErrorMessage(res, at, "Ошибка"));
    }
  }

  async function deletePromo(promo) {
    const res = await api(`/admin/promos/${promo.id}`, { method: "DELETE" });
    if (res?.ok) {
      state.update((s) => ({
        ...s,
        promos: s.promos.filter((p) => p.id !== promo.id),
      }));
      onToast("Промокод удалён");
    } else {
      onToast(adminErrorMessage(res, at, "Ошибка"));
    }
  }

  function setPage(page) {
    state.update((s) => ({ ...s, promosPage: page }));
    loadPromos();
  }

  function setCreateOpen(open) {
    state.update((s) => ({ ...s, promoCreateOpen: open }));
  }

  function updateDraft(fields) {
    state.update((s) => ({ ...s, promoDraft: { ...s.promoDraft, ...fields } }));
  }

  return {
    subscribe: state.subscribe,
    set: state.set,
    update: state.update,
    loadPromos,
    createPromo,
    togglePromo,
    deletePromo,
    setPage,
    setCreateOpen,
    updateDraft,
    PROMOS_PAGE_SIZE,
  };
}
