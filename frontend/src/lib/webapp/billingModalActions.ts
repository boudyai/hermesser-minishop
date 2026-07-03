import type { BillingPlan, PaymentMethod, TariffCatalogEntry } from "./tariffs";

type WebappRecord = Record<string, unknown>;

type BillingModalStore = {
  closeDeviceTopupModal: () => void;
  openDeviceTopupModal: (defaultMethod?: string) => void;
  openPaymentModal: (
    tariffMode: boolean,
    singleTariffMode: boolean,
    tariffCatalog: WebappRecord[],
    subscription: WebappRecord,
    plans: WebappRecord[],
    defaultMethod?: string
  ) => void;
  openTariffChangeModal: (defaultMethod?: string) => void;
  openTopupModal: (kind?: string, defaultMethod?: string) => void;
};

type DevicesActionsStore = {
  disconnectDevice: (devicesEnabled: boolean) => unknown;
  loadDevices: (devicesEnabled: boolean, force?: boolean) => unknown;
};

type BillingModalActionDeps = {
  billingStore: BillingModalStore;
  devicesEnabled: () => boolean;
  devicesStore: DevicesActionsStore;
  methods: () => PaymentMethod[];
  plans: () => BillingPlan[];
  singleTariffMode: () => boolean;
  subscription: () => WebappRecord;
  tariffCatalog: () => TariffCatalogEntry[];
  tariffMode: () => boolean;
};

export function defaultPaymentMethod(methods: PaymentMethod[] | null | undefined): string {
  return String(methods?.[0]?.id || "");
}

export function createBillingModalActions({
  billingStore,
  devicesEnabled,
  devicesStore,
  methods,
  plans,
  singleTariffMode,
  subscription,
  tariffCatalog,
  tariffMode,
}: BillingModalActionDeps) {
  function currentDefaultPaymentMethod() {
    return defaultPaymentMethod(methods());
  }

  function openPaymentModal(preferredTariffKey: string = "") {
    // ponytail: when the onboarding wizard pre-selects a hosting
    // plan (hosting_basic / hosting_plus) we forward it through so
    // the payment modal lands directly on the matching plan with
    // included_cornllm_balance_rub already wired into the activation
    // path. Without this the wizard would default to whichever
    // tariff is_default and the user would never see Plus.
    billingStore.openPaymentModal(
      tariffMode(),
      singleTariffMode(),
      tariffCatalog(),
      subscription(),
      plans(),
      currentDefaultPaymentMethod(),
      preferredTariffKey ? { preferredTariffKey } : {}
    );
  }

  function openTopupModal(kind: string) {
    billingStore.openTopupModal(kind, currentDefaultPaymentMethod());
  }

  function openRegularTopupModal() {
    openTopupModal("regular");
  }

  function openPremiumTopupModal() {
    openTopupModal("premium");
  }

  function openTariffChangeModal() {
    billingStore.openTariffChangeModal(currentDefaultPaymentMethod());
  }

  function openDeviceTopupModal() {
    billingStore.openDeviceTopupModal(currentDefaultPaymentMethod());
  }

  function closeDeviceTopupModal() {
    billingStore.closeDeviceTopupModal();
  }

  function loadDevices(force = false) {
    return devicesStore.loadDevices(devicesEnabled(), force);
  }

  function disconnectDevice() {
    return devicesStore.disconnectDevice(devicesEnabled());
  }

  return {
    defaultPaymentMethod: currentDefaultPaymentMethod,
    openPaymentModal,
    openTopupModal,
    openRegularTopupModal,
    openPremiumTopupModal,
    openTariffChangeModal,
    openDeviceTopupModal,
    closeDeviceTopupModal,
    loadDevices,
    disconnectDevice,
  };
}
