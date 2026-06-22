import { writable, get } from "svelte/store";
import type { LoadDataOptions } from "../dataClient";
import type { BillingActions } from "../billingActions";
import { unwrap } from "../publicApi";

type TelegramWebApp = Record<string, unknown> & {
  openInvoice?: (url: string, callback: (status: string) => void) => void;
};
type BillingRecord = Record<string, unknown> & {
  action?: string;
  actions?: BillingRecord[];
  available?: boolean;
  hwid_renewal?: BillingRecord;
  key?: string;
  message?: string;
  mode?: string;
  paid?: boolean;
  payment_id?: string | number;
  payment_url?: string | null;
  plans?: BillingRecord[];
  sale_mode?: string;
  status?: string;
  tariff_key?: string;
  targets?: BillingRecord[];
  topup_kind?: string;
};
type BillingOkRecord = BillingRecord & { ok: boolean };
type BillingState = {
  paymentModalOpen: boolean;
  paymentStep: string;
  selectedTariffKey: string;
  selectedPlan: BillingRecord | null;
  selectedMethod: string;
  renewHwidDevices: boolean;
  paymentStartedWithActiveSubscription: boolean;
  topupModalOpen: boolean;
  topupKind: string;
  deviceTopupModalOpen: boolean;
  changeModalOpen: boolean;
  topupOptions: BillingRecord | null;
  deviceTopupOptions: BillingRecord | null;
  changeOptions: BillingRecord | null;
  selectedTopupPlan: BillingRecord | null;
  selectedDeviceTopupPlan: BillingRecord | null;
  selectedChangeTarget: BillingRecord | null;
  selectedChangeAction: BillingRecord | null;
  changeConfirmOpen: boolean;
  tariffActionBusy: boolean;
  payBusy: boolean;
};

export function createBillingStore({
  billing,
  loadData,
  t,
  showToast,
  openExternalLink,
  onSubscriptionActivationPending = null,
  onSubscriptionActivated = null,
  tg,
  getTg = null,
  telegramSdk = null,
}: {
  billing: BillingActions;
  loadData: (options?: LoadDataOptions & Record<string, unknown>) => Promise<unknown>;
  t: (key: string, params?: Record<string, unknown>, fallback?: string) => string;
  showToast: (message: string) => void;
  openExternalLink: (url: string) => void;
  onSubscriptionActivationPending?: ((context: Record<string, unknown>) => void) | null;
  onSubscriptionActivated?: ((context: Record<string, unknown>) => Promise<void> | void) | null;
  tg?: TelegramWebApp | null;
  getTg?: (() => TelegramWebApp | null) | null;
  telegramSdk?: {
    refresh?: () => TelegramWebApp | null;
    ensureForAction?: () => Promise<TelegramWebApp | null>;
  } | null;
}) {
  function asRecord(value: unknown): BillingRecord {
    return value && typeof value === "object" ? (value as BillingRecord) : {};
  }

  function arrayRecords(value: unknown): BillingRecord[] {
    return Array.isArray(value) ? value.filter((item) => item && typeof item === "object") : [];
  }

  function stringField(value: unknown): string {
    return typeof value === "string" ? value : "";
  }

  function unwrapBilling<T extends { ok: boolean }>(response: T): T & BillingRecord {
    return unwrap(response) as T & BillingRecord;
  }

  const state = writable<BillingState>({
    paymentModalOpen: false,
    paymentStep: "tariff",
    selectedTariffKey: "",
    selectedPlan: null,
    selectedMethod: "",
    renewHwidDevices: true,
    paymentStartedWithActiveSubscription: false,
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
  let paymentPollToken = 0;
  const successfulPaymentIds = new Set<string>();

  function sleep(ms: number) {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }

  function isSubscriptionSale(plan: BillingRecord | null) {
    const saleMode = String(plan?.sale_mode || "subscription").toLowerCase();
    return ![
      "traffic",
      "traffic_package",
      "topup",
      "premium_topup",
      "hwid_devices",
      "hwid_devices_renewal",
    ].includes(saleMode);
  }

  function paymentSuccessContext(s: BillingState, response: BillingRecord = {}) {
    return {
      paymentId: response.payment_id || "",
      initialSubscriptionPayment:
        !s.paymentStartedWithActiveSubscription && isSubscriptionSale(s.selectedPlan),
      renewalSubscriptionPayment:
        s.paymentStartedWithActiveSubscription && isSubscriptionSale(s.selectedPlan),
    };
  }

  async function handlePaymentSuccess(successContext: BillingRecord = {}) {
    const paymentId = String(successContext.paymentId || "");
    if (paymentId && successfulPaymentIds.has(paymentId)) return;
    if (paymentId) {
      successfulPaymentIds.add(paymentId);
      paymentPollToken += 1;
    }
    showToast(t("wa_payment_success", {}, "Payment successful"));
    await loadData({ fresh: true });
    if (
      successContext.initialSubscriptionPayment &&
      typeof onSubscriptionActivated === "function"
    ) {
      await onSubscriptionActivated({ source: "payment", ...successContext });
    }
  }

  function rememberSubscriptionActivationPending(successContext: BillingRecord = {}) {
    if (
      !successContext.initialSubscriptionPayment ||
      typeof onSubscriptionActivationPending !== "function"
    ) {
      return;
    }
    try {
      onSubscriptionActivationPending({ source: "payment", ...successContext });
    } catch (_error) {
      void _error;
    }
  }

  function openPaymentModal(
    tariffMode: boolean,
    singleTariffMode: boolean,
    tariffCatalog: BillingRecord[],
    subscription: BillingRecord,
    plans: BillingRecord[],
    defaultMethod = "",
    options: BillingRecord = {}
  ) {
    state.update((s) => {
      let step: string;
      let plan = s.selectedPlan;
      let tariffKey = s.selectedTariffKey;
      const catalog = tariffCatalog || [];
      const planList = plans || [];
      const preferredTariffKey = String(options?.preferredTariffKey || "").trim();
      const preferredTariff = preferredTariffKey
        ? catalog.find((tariff) => tariff.key === preferredTariffKey)
        : null;
      const fallbackTariff =
        catalog.find((tariff) => tariff.is_default) ||
        catalog.find((tariff) => tariff.key === "standard") ||
        catalog[0] ||
        null;
      const deeplinkTariff =
        preferredTariff || (options?.selectDefaultTariff ? fallbackTariff : null);

      if (tariffMode) {
        if (deeplinkTariff?.key) {
          tariffKey = String(deeplinkTariff.key);
          plan = planList.find((p) => p?.tariff_key === tariffKey) || null;
          step = options?.preferCheckout && plan ? "checkout" : "tariff";
        } else if (singleTariffMode && catalog[0]?.key) {
          tariffKey = String(catalog[0].key);
          plan = planList.find((p) => p?.tariff_key === tariffKey) || null;
          step = "checkout";
        } else if (
          subscription?.active &&
          subscription?.tariff_key &&
          catalog.some((t) => t.key === subscription.tariff_key)
        ) {
          tariffKey = String(subscription.tariff_key);
          plan = planList.find((p) => p?.tariff_key === tariffKey) || null;
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
        renewHwidDevices: true,
        paymentStartedWithActiveSubscription: Boolean(subscription?.active),
      };
    });
  }

  function closePaymentModal() {
    state.update((s) => ({ ...s, paymentModalOpen: false }));
  }

  function selectTariff(tariff: BillingRecord, plans: BillingRecord[] = []) {
    const key = String(tariff?.key || "").trim();
    if (!key) return;
    state.update((s) => ({
      ...s,
      selectedTariffKey: key,
      selectedPlan: plans.find((plan) => plan?.tariff_key === key) || null,
      renewHwidDevices: true,
    }));
  }

  function continueWithSelectedTariff(selectedTariffPlans: BillingRecord[] = []) {
    state.update((s) => {
      if (!s.selectedTariffKey) return s;
      return {
        ...s,
        selectedPlan: s.selectedPlan || selectedTariffPlans[0] || null,
        paymentStep: "checkout",
        renewHwidDevices: true,
      };
    });
  }

  function backToTariffList(subscription: BillingRecord, tariffCatalog: BillingRecord[] = []) {
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
      deviceTopupOptions: null,
      selectedDeviceTopupPlan: null,
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

  function resolveTelegramWebApp() {
    if (typeof getTg === "function") {
      const currentTg = getTg();
      if (currentTg) return currentTg;
    }
    if (tg) return tg;
    if (telegramSdk?.refresh) return telegramSdk.refresh();
    return null;
  }

  async function resolveInvoiceTelegramWebApp(): Promise<TelegramWebApp | null> {
    const currentTg = resolveTelegramWebApp();
    if (currentTg?.openInvoice) return currentTg;
    if (telegramSdk?.ensureForAction) {
      const loadedTg = await telegramSdk.ensureForAction();
      if (loadedTg?.openInvoice) return loadedTg;
    }
    return resolveTelegramWebApp();
  }

  async function openTelegramInvoice(url: string, successContext: BillingRecord = {}) {
    if (!url) return false;
    const invoiceTg = await resolveInvoiceTelegramWebApp();
    if (invoiceTg?.openInvoice) {
      invoiceTg.openInvoice(url, async (status) => {
        if (status === "paid") {
          await handlePaymentSuccess(successContext);
        } else if (status === "failed") {
          showToast(t("wa_payment_create_failed"));
        }
      });
      return true;
    }
    showToast(
      t("wa_payment_stars_telegram_required", {}, "Open this payment in Telegram to pay with Stars")
    );
    return false;
  }

  async function handlePaymentResponse(
    response: BillingOkRecord,
    successContext: BillingRecord = {},
    closeModal: () => void = () => {}
  ) {
    if (!response.ok) throw response;
    const payload = unwrapBilling(response);
    showToast(t("wa_payment_created"));
    if (payload.action === "open_invoice") {
      if (!payload.payment_url) throw response;
      const opened = await openTelegramInvoice(payload.payment_url, successContext);
      if (!opened) return false;
    } else if (payload.action === "invoice_sent") {
      startPaymentStatusPolling(payload.payment_id, successContext);
      closeModal();
      return true;
    } else {
      if (!payload.payment_url) throw response;
      openExternalLink(payload.payment_url);
    }
    startPaymentStatusPolling(payload.payment_id, successContext);
    closeModal();
    return true;
  }

  function startPaymentStatusPolling(
    paymentId: string | number | undefined,
    successContext: BillingRecord = {}
  ) {
    if (!paymentId || !billing.fetchPaymentStatus) return;
    const token = ++paymentPollToken;
    void (async () => {
      for (let attempt = 0; attempt < 45 && token === paymentPollToken; attempt += 1) {
        await sleep(attempt === 0 ? 1500 : 2000);
        if (token !== paymentPollToken) return;
        try {
          const status = await billing.fetchPaymentStatus(paymentId);
          if (!status?.ok) continue;
          const payload = unwrapBilling(status);
          if (payload.paid || payload.status === "succeeded") {
            await handlePaymentSuccess({ ...successContext, paymentId });
            return;
          }
          const normalized = String(payload.status || "").toLowerCase();
          if (
            normalized === "failed" ||
            normalized === "canceled" ||
            normalized === "cancelled" ||
            normalized.startsWith("failed_")
          ) {
            showToast(t("wa_payment_create_failed"));
            return;
          }
        } catch (_error) {
          void _error;
        }
      }
    })();
  }

  async function createPayment() {
    const s = get(state);
    if (!s.selectedPlan || !s.selectedMethod || s.payBusy) return;
    state.update((s) => ({ ...s, payBusy: true }));
    try {
      const response = await billing.postPayment(
        billing.planPaymentBody(s.selectedPlan, s.selectedMethod, {
          renewHwidDevices: s.renewHwidDevices && Boolean(s.selectedPlan?.hwid_renewal?.available),
        })
      );
      const successContext = paymentSuccessContext(s, response);
      rememberSubscriptionActivationPending(successContext);
      await handlePaymentResponse(response, successContext, () => {
        state.update((s) => ({ ...s, paymentModalOpen: false }));
      });
    } catch (error: unknown) {
      showToast(stringField(asRecord(error).message) || t("wa_payment_create_failed"));
    } finally {
      state.update((s) => ({ ...s, payBusy: false }));
    }
  }

  async function loadTopupOptions(kind: string) {
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
      const payload = unwrapBilling(response);
      state.update((s) => ({
        ...s,
        topupOptions: payload,
        selectedTopupPlan: arrayRecords(payload.plans)[0] || null,
      }));
    } catch (error: unknown) {
      if (requestId !== topupOptionsRequestId || kind !== get(state).topupKind) return;
      showToast(stringField(asRecord(error).message) || t("wa_tariff_options_failed"));
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
        billing.topupPaymentBody(
          s.selectedTopupPlan,
          s.selectedMethod,
          stringField(s.topupOptions?.tariff_key)
        )
      );
      await handlePaymentResponse(response, {}, () => {
        state.update((s) => ({ ...s, topupModalOpen: false }));
      });
    } catch (error: unknown) {
      showToast(stringField(asRecord(error).message) || t("wa_payment_create_failed"));
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
      const payload = unwrapBilling(response);
      const targets = arrayRecords(payload.targets);
      const firstTarget = targets[0] || null;
      state.update((s) => ({
        ...s,
        changeOptions: payload,
        selectedChangeTarget: firstTarget,
        selectedChangeAction: firstTarget?.actions?.[0] || null,
      }));
    } catch (error: unknown) {
      showToast(stringField(asRecord(error).message) || t("wa_tariff_options_failed"));
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
        tariff_key: stringField(s.selectedChangeTarget.tariff_key),
        mode: stringField(s.selectedChangeAction.mode),
      });
      if (!response?.ok) throw response;
      unwrapBilling(response);
      showToast(t("wa_tariff_change_applied"));
      state.update((s) => ({
        ...s,
        changeConfirmOpen: false,
        changeModalOpen: false,
        changeOptions: null,
      }));
      await loadData();
    } catch (error: unknown) {
      showToast(stringField(asRecord(error).message) || t("wa_tariff_change_failed"));
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
      await handlePaymentResponse(response, {}, () => {
        state.update((s) => ({ ...s, changeConfirmOpen: false, changeModalOpen: false }));
      });
    } catch (error: unknown) {
      showToast(stringField(asRecord(error).message) || t("wa_payment_create_failed"));
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
      const payload = unwrapBilling(response);
      state.update((s) => ({
        ...s,
        deviceTopupOptions: payload,
        selectedDeviceTopupPlan: arrayRecords(payload.plans)[0] || null,
      }));
    } catch (error: unknown) {
      showToast(stringField(asRecord(error).message) || t("wa_device_topup_options_failed"));
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
          stringField(s.deviceTopupOptions?.tariff_key)
        )
      );
      await handlePaymentResponse(response, {}, () => {
        state.update((s) => ({ ...s, deviceTopupModalOpen: false }));
      });
    } catch (error: unknown) {
      showToast(stringField(asRecord(error).message) || t("wa_payment_create_failed"));
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
