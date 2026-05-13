import { writable, get } from "svelte/store";

export function createBillingStore({ billing, loadData, t, showToast, openExternalLink, tg }) {
  const state = writable({
    paymentModalOpen: false,
    paymentStep: "tariff",
    selectedTariffKey: "",
    selectedPlan: null,
    selectedMethod: "",
    topupModalOpen: false,
    topupKind: "regular",
    deviceTopupModalOpen: false,
    changeModalOpen: false,
    topupOptions: null,
    deviceTopupOptions: null,
    changeOptions: null,
    selectedTopupPlan: null,
    selectedDeviceTopupPlan: null,
    selectedChangeTarget: null,
    selectedChangeAction: null,
    changeConfirmOpen: false,
    tariffActionBusy: false,
    payBusy: false,
  });

  let topupOptionsRequestId = 0;

  function openPaymentModal(
    tariffMode,
    singleTariffMode,
    tariffCatalog,
    subscription,
    plans,
    defaultMethod = ""
  ) {
    state.update((s) => {
      let step;
      let plan = s.selectedPlan;
      let tariffKey = s.selectedTariffKey;

      if (tariffMode) {
        if (singleTariffMode && tariffCatalog[0]?.key) {
          tariffKey = tariffCatalog[0].key;
          plan = plans.find((p) => p?.tariff_key === tariffKey) || null;
          step = "checkout";
        } else if (
          subscription?.active &&
          subscription?.tariff_key &&
          tariffCatalog.some((t) => t.key === subscription.tariff_key)
        ) {
          tariffKey = subscription.tariff_key;
          plan = plans.find((p) => p?.tariff_key === tariffKey) || null;
          step = "checkout";
        } else {
          step = "tariff";
          tariffKey = "";
          plan = null;
        }
      } else {
        step = "checkout";
      }
      return {
        ...s,
        paymentModalOpen: true,
        paymentStep: step,
        selectedTariffKey: tariffKey,
        selectedPlan: plan,
        selectedMethod: s.selectedMethod || defaultMethod,
      };
    });
  }

  function closePaymentModal() {
    state.update((s) => ({ ...s, paymentModalOpen: false }));
  }

  function selectTariff(tariff, plans = []) {
    const key = String(tariff?.key || "").trim();
    if (!key) return;
    state.update((s) => ({
      ...s,
      selectedTariffKey: key,
      selectedPlan: plans.find((plan) => plan?.tariff_key === key) || null,
    }));
  }

  function continueWithSelectedTariff(selectedTariffPlans = []) {
    state.update((s) => {
      if (!s.selectedTariffKey) return s;
      return {
        ...s,
        selectedPlan: s.selectedPlan || selectedTariffPlans[0] || null,
        paymentStep: "checkout",
      };
    });
  }

  function backToTariffList(subscription, tariffCatalog = []) {
    if (
      subscription?.active &&
      subscription?.tariff_key &&
      tariffCatalog.some((t) => t.key === subscription.tariff_key)
    ) {
      return;
    }
    state.update((s) => ({ ...s, paymentStep: "tariff" }));
  }

  function openTopupModal(kind = "regular", defaultMethod = "") {
    const normalizedKind = kind === "premium" ? "premium" : "regular";
    state.update((s) => ({
      ...s,
      topupKind: normalizedKind,
      topupModalOpen: true,
      topupOptions: s.topupOptions?.topup_kind === normalizedKind ? s.topupOptions : null,
      selectedTopupPlan: s.topupOptions?.topup_kind === normalizedKind ? s.selectedTopupPlan : null,
      selectedMethod: s.selectedMethod || defaultMethod,
    }));
    loadTopupOptions(normalizedKind);
  }

  function closeTopupModal() {
    state.update((s) => ({ ...s, topupModalOpen: false }));
  }

  function openDeviceTopupModal(defaultMethod = "") {
    state.update((s) => ({
      ...s,
      deviceTopupModalOpen: true,
      selectedMethod: s.selectedMethod || defaultMethod,
    }));
    loadDeviceTopupOptions();
  }

  function closeDeviceTopupModal() {
    state.update((s) => ({ ...s, deviceTopupModalOpen: false }));
  }

  function openTariffChangeModal(defaultMethod = "") {
    state.update((s) => ({
      ...s,
      changeModalOpen: true,
      selectedMethod: s.selectedMethod || defaultMethod,
    }));
    loadTariffChangeOptions();
  }

  function closeTariffChangeModal() {
    state.update((s) => ({ ...s, changeModalOpen: false }));
  }

  function openTariffChangeConfirm() {
    const s = get(state);
    if (!s.selectedChangeTarget || !s.selectedChangeAction) return;
    state.update((s) => ({ ...s, changeConfirmOpen: true }));
  }

  function closeTariffChangeConfirm() {
    state.update((s) => ({ ...s, changeConfirmOpen: false }));
  }

  function openTelegramInvoice(url) {
    if (!url) return;
    if (tg?.openInvoice) {
      tg.openInvoice(url, (status) => {
        if (status === "paid") {
          showToast(t("wa_payment_success", {}, "Payment successful"));
          loadData();
        } else if (status === "failed") {
          showToast(t("wa_payment_create_failed"));
        }
      });
      return;
    }
    openExternalLink(url);
  }

  async function createPayment() {
    const s = get(state);
    if (!s.selectedPlan || !s.selectedMethod || s.payBusy) return;
    state.update((s) => ({ ...s, payBusy: true }));
    try {
      const response = await billing.postPayment(
        billing.planPaymentBody(s.selectedPlan, s.selectedMethod)
      );
      if (!response.ok) throw response;
      showToast(t("wa_payment_created"));
      if (response.action === "open_invoice") {
        if (!response.payment_url) throw response;
        openTelegramInvoice(response.payment_url);
      } else if (response.action === "invoice_sent") {
        state.update((s) => ({ ...s, paymentModalOpen: false }));
        return;
      } else {
        if (!response.payment_url) throw response;
        openExternalLink(response.payment_url);
      }
      state.update((s) => ({ ...s, paymentModalOpen: false }));
    } catch (error) {
      showToast(error?.message || t("wa_payment_create_failed"));
    } finally {
      state.update((s) => ({ ...s, payBusy: false }));
    }
  }

  async function loadTopupOptions(kind) {
    const s = get(state);
    if (s.topupOptions?.topup_kind === kind) return;
    const requestId = ++topupOptionsRequestId;
    state.update((s) => ({
      ...s,
      tariffActionBusy: true,
      topupOptions: null,
      selectedTopupPlan: null,
    }));
    try {
      const response = await billing.fetchTopupOptions(kind);
      if (requestId !== topupOptionsRequestId || kind !== get(state).topupKind) return;
      if (!response?.ok) throw response;
      state.update((s) => ({
        ...s,
        topupOptions: response,
        selectedTopupPlan: response.plans?.[0] || null,
      }));
    } catch (error) {
      if (requestId !== topupOptionsRequestId || kind !== get(state).topupKind) return;
      showToast(error?.message || t("wa_tariff_options_failed"));
      state.update((s) => ({ ...s, topupModalOpen: false }));
    } finally {
      if (requestId === topupOptionsRequestId) {
        state.update((s) => ({ ...s, tariffActionBusy: false }));
      }
    }
  }

  async function createTopupPayment() {
    const s = get(state);
    if (!s.selectedTopupPlan || !s.selectedMethod || s.payBusy) return;
    state.update((s) => ({ ...s, payBusy: true }));
    try {
      const response = await billing.postPayment(
        billing.topupPaymentBody(s.selectedTopupPlan, s.selectedMethod, s.topupOptions?.tariff_key)
      );
      if (!response.ok || !response.payment_url) throw response;
      showToast(t("wa_payment_created"));
      openExternalLink(response.payment_url);
      state.update((s) => ({ ...s, topupModalOpen: false }));
    } catch (error) {
      showToast(error?.message || t("wa_payment_create_failed"));
    } finally {
      state.update((s) => ({ ...s, payBusy: false }));
    }
  }

  async function loadTariffChangeOptions() {
    const s = get(state);
    if (s.changeOptions || s.tariffActionBusy) return;
    state.update((s) => ({ ...s, tariffActionBusy: true }));
    try {
      const response = await billing.fetchTariffChangeOptions();
      if (!response?.ok) throw response;
      state.update((s) => ({
        ...s,
        changeOptions: response,
        selectedChangeTarget: response.targets?.[0] || null,
        selectedChangeAction: response.targets?.[0]?.actions?.[0] || null,
      }));
    } catch (error) {
      showToast(error?.message || t("wa_tariff_options_failed"));
      state.update((s) => ({ ...s, changeModalOpen: false }));
    } finally {
      state.update((s) => ({ ...s, tariffActionBusy: false }));
    }
  }

  async function applyTariffChange() {
    const s = get(state);
    if (!s.selectedChangeTarget || !s.selectedChangeAction || s.tariffActionBusy) return;
    if (s.selectedChangeAction.kind === "payment") {
      await createTariffChangePayment();
      return;
    }
    state.update((s) => ({ ...s, tariffActionBusy: true }));
    try {
      const response = await billing.postTariffChange({
        tariff_key: s.selectedChangeTarget.tariff_key,
        mode: s.selectedChangeAction.mode,
      });
      if (!response?.ok) throw response;
      showToast(t("wa_tariff_change_applied"));
      state.update((s) => ({
        ...s,
        changeConfirmOpen: false,
        changeModalOpen: false,
        changeOptions: null,
      }));
      await loadData();
    } catch (error) {
      showToast(error?.message || t("wa_tariff_change_failed"));
    } finally {
      state.update((s) => ({ ...s, tariffActionBusy: false }));
    }
  }

  async function createTariffChangePayment() {
    const s = get(state);
    if (!s.selectedChangeTarget || !s.selectedChangeAction || !s.selectedMethod || s.payBusy)
      return;
    state.update((s) => ({ ...s, payBusy: true }));
    try {
      const body = billing.changePaymentBody(
        s.selectedChangeAction,
        s.selectedChangeTarget,
        s.selectedMethod
      );
      const response =
        s.selectedChangeAction.mode === "buy_package" ||
        s.selectedChangeAction.mode === "buy_period"
          ? await billing.postPayment(body)
          : await billing.postTariffChangePayment(body);
      if (!response.ok || !response.payment_url) throw response;
      showToast(t("wa_payment_created"));
      openExternalLink(response.payment_url);
      state.update((s) => ({ ...s, changeConfirmOpen: false, changeModalOpen: false }));
    } catch (error) {
      showToast(error?.message || t("wa_payment_create_failed"));
    } finally {
      state.update((s) => ({ ...s, payBusy: false }));
    }
  }

  async function loadDeviceTopupOptions() {
    const s = get(state);
    if (s.deviceTopupOptions || s.tariffActionBusy) return;
    state.update((s) => ({ ...s, tariffActionBusy: true }));
    try {
      const response = await billing.fetchDeviceTopupOptions();
      if (!response?.ok) throw response;
      state.update((s) => ({
        ...s,
        deviceTopupOptions: response,
        selectedDeviceTopupPlan: response.plans?.[0] || null,
      }));
    } catch (error) {
      showToast(error?.message || t("wa_device_topup_options_failed"));
      state.update((s) => ({ ...s, deviceTopupModalOpen: false }));
    } finally {
      state.update((s) => ({ ...s, tariffActionBusy: false }));
    }
  }

  async function createDeviceTopupPayment() {
    const s = get(state);
    if (!s.selectedDeviceTopupPlan || !s.selectedMethod || s.payBusy) return;
    state.update((s) => ({ ...s, payBusy: true }));
    try {
      const response = await billing.postPayment(
        billing.deviceTopupPaymentBody(
          s.selectedDeviceTopupPlan,
          s.selectedMethod,
          s.deviceTopupOptions?.tariff_key
        )
      );
      if (!response.ok || !response.payment_url) throw response;
      showToast(t("wa_payment_created"));
      openExternalLink(response.payment_url);
      state.update((s) => ({ ...s, deviceTopupModalOpen: false }));
    } catch (error) {
      showToast(error?.message || t("wa_payment_create_failed"));
    } finally {
      state.update((s) => ({ ...s, payBusy: false }));
    }
  }

  return {
    subscribe: state.subscribe,
    set: state.set,
    update: state.update,
    openPaymentModal,
    closePaymentModal,
    selectTariff,
    continueWithSelectedTariff,
    backToTariffList,
    createPayment,
    openTopupModal,
    closeTopupModal,
    loadTopupOptions,
    createTopupPayment,
    openTariffChangeModal,
    closeTariffChangeModal,
    openTariffChangeConfirm,
    closeTariffChangeConfirm,
    loadTariffChangeOptions,
    applyTariffChange,
    createTariffChangePayment,
    openDeviceTopupModal,
    closeDeviceTopupModal,
    loadDeviceTopupOptions,
    createDeviceTopupPayment,
  };
}
