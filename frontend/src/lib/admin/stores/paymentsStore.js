import { writable } from "svelte/store";
import { withRoutePrefix } from "../../webapp/routes.js";
import { adminErrorMessage } from "../errors.js";

export function createPaymentsStore({
  api,
  onToast = () => {},
  at = (key, _params, fallback) => fallback || key,
  routePrefix = "",
}) {
  const state = writable({
    payments: [],
    paymentsTotal: 0,
    paymentsPage: 0,
    paymentsLoading: false,
    openedPaymentId: null,
    openedPayment: null,
    paymentDetailLoading: false,
  });

  const PAYMENTS_PAGE_SIZE = 25;
  let active = "stats";

  function setActive(section) {
    active = section;
  }

  function pushPaymentPath(paymentId) {
    if (typeof window === "undefined" || window.location.protocol === "file:") return;
    if (active !== "payments") return;
    const target = withRoutePrefix(
      paymentId ? `/admin/payments/${paymentId}` : "/admin/payments",
      routePrefix
    );
    if (window.location.pathname === target) return;
    window.history.pushState(null, "", `${target}${window.location.search}${window.location.hash}`);
  }

  async function loadPayments() {
    state.update((s) => ({ ...s, paymentsLoading: true }));
    let currentPage = 0;
    state.update((s) => {
      currentPage = s.paymentsPage;
      return s;
    });

    try {
      const data = await api(`/admin/payments?page=${currentPage}&page_size=${PAYMENTS_PAGE_SIZE}`);
      if (data?.ok) {
        state.update((s) => ({
          ...s,
          payments: data.payments || [],
          paymentsTotal: data.total || 0,
        }));
      }
    } finally {
      state.update((s) => ({ ...s, paymentsLoading: false }));
    }
  }

  function setPage(page) {
    state.update((s) => ({ ...s, paymentsPage: page }));
    loadPayments();
  }

  async function openPayment(paymentOrId, opts = {}) {
    const paymentId =
      typeof paymentOrId === "object" && paymentOrId !== null
        ? Number(paymentOrId.payment_id)
        : Number(paymentOrId);
    if (!Number.isFinite(paymentId) || paymentId <= 0) return;

    state.update((s) => ({
      ...s,
      openedPaymentId: paymentId,
      openedPayment:
        typeof paymentOrId === "object" && paymentOrId !== null
          ? { ...paymentOrId }
          : s.openedPayment?.payment_id === paymentId
            ? s.openedPayment
            : null,
      paymentDetailLoading: true,
    }));
    if (!opts.skipPush) pushPaymentPath(paymentId);

    try {
      const res = await api(`/admin/payments/${paymentId}`);
      if (res?.ok) {
        state.update((s) => ({
          ...s,
          openedPayment: res.payment || s.openedPayment,
        }));
      } else {
        onToast(
          adminErrorMessage(res, at, at("payment_load_failed", {}, "Не удалось загрузить платеж"))
        );
        state.update((s) => ({ ...s, openedPaymentId: null, openedPayment: null }));
        if (!opts.skipPush) pushPaymentPath(null);
      }
    } finally {
      state.update((s) => ({ ...s, paymentDetailLoading: false }));
    }
  }

  function closePayment(opts = {}) {
    let wasOpen = false;
    state.update((s) => {
      wasOpen = Boolean(s.openedPaymentId);
      return {
        ...s,
        openedPaymentId: null,
        openedPayment: null,
        paymentDetailLoading: false,
      };
    });
    if (wasOpen && !opts.skipPush) pushPaymentPath(null);
  }

  function copyToClipboard(text, successMessage = at("copied", {}, "Скопировано")) {
    if (!text) return;
    if (typeof navigator !== "undefined" && navigator?.clipboard?.writeText) {
      navigator.clipboard.writeText(String(text)).then(
        () => onToast(successMessage),
        () => onToast(String(text))
      );
    } else {
      onToast(String(text));
    }
  }

  return {
    subscribe: state.subscribe,
    set: state.set,
    update: state.update,
    setActive,
    loadPayments,
    setPage,
    openPayment,
    closePayment,
    copyToClipboard,
  };
}
