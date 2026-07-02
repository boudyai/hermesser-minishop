type PromoTrialStore = {
  activateTrial: (botToken?: string) => unknown;
  applyPromo: () => unknown;
  clearPromoFieldError: () => void;
  openPromoCheckout: () => void;
  setPromoCode: (value: string) => void;
};

type PromoTrialActionDeps = {
  actionsStore: PromoTrialStore;
};

export function createPromoTrialActions({ actionsStore }: PromoTrialActionDeps) {
  function applyPromo() {
    return actionsStore.applyPromo();
  }

  function setPromoCode(value: string) {
    actionsStore.setPromoCode(value);
  }

  function clearPromoFieldError() {
    actionsStore.clearPromoFieldError();
  }

  function openPromoCheckout() {
    actionsStore.openPromoCheckout();
  }

  function activateTrial(botToken?: string) {
    return actionsStore.activateTrial(botToken);
  }

  return {
    activateTrial,
    applyPromo,
    clearPromoFieldError,
    openPromoCheckout,
    setPromoCode,
  };
}
