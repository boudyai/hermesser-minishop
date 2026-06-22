import { writable, get } from "svelte/store";
import type { LoadDataOptions } from "../dataClient";
import type { ApiClient, PostPayload, TrialActivateResponse } from "../publicApi";
import { unwrap } from "../publicApi";

type Translate = (key: string, params?: Record<string, unknown>, fallback?: string) => string;
type MaybeRecord = Record<string, unknown>;
type ActionsState = {
  promoCode: string;
  promoBusy: boolean;
  promoStatus: string;
  promoIsError: boolean;
  promoFieldError: string;
  trialBusy: boolean;
  trialActivationResult: Extract<TrialActivateResponse, { ok: true }> | null;
  trialActivationError: string;
};
type ActionsStoreDeps = {
  api: ApiClient["api"];
  t: Translate;
  showToast: (message: string) => void;
  loadData: (options?: LoadDataOptions & Record<string, unknown>) => Promise<unknown>;
  maybeShowActivationSuccessDialog: (context?: Record<string, unknown>) => Promise<boolean>;
};

function asRecord(value: unknown): MaybeRecord {
  return value && typeof value === "object" ? (value as MaybeRecord) : {};
}

function stringField(value: unknown): string {
  return typeof value === "string" ? value : "";
}

export function createActionsStore({
  api,
  t,
  showToast,
  loadData,
  maybeShowActivationSuccessDialog,
}: ActionsStoreDeps) {
  const state = writable<ActionsState>({
    promoCode: "",
    promoBusy: false,
    promoStatus: "",
    promoIsError: false,
    promoFieldError: "",
    trialBusy: false,
    trialActivationResult: null,
    trialActivationError: "",
  });

  function setPromoCode(value: string) {
    state.update((s) => ({ ...s, promoCode: value }));
  }

  function setPromoFieldError(value: string) {
    state.update((s) => ({ ...s, promoFieldError: value }));
  }

  function clearPromoFieldError() {
    setPromoFieldError("");
  }

  function trialActivationFailureMessage(error: unknown) {
    const errorRecord = asRecord(error);
    if (
      errorRecord.error === "trial_telegram_required" ||
      errorRecord.message === "telegram_required" ||
      errorRecord.message === "disposable_email"
    ) {
      return t(
        "wa_trial_telegram_required_error",
        {},
        "Для активации пробного периода привяжите Telegram."
      );
    }
    return stringField(errorRecord.message) || t("wa_trial_activation_failed");
  }

  function referralWelcomeFailureMessage(error: unknown) {
    const errorRecord = asRecord(error);
    if (
      errorRecord.error === "referral_welcome_telegram_required" ||
      errorRecord.message === "telegram_required" ||
      errorRecord.message === "disposable_email"
    ) {
      return t(
        "wa_referral_welcome_telegram_required_error",
        {},
        "Для получения реферального бонуса привяжите Telegram."
      );
    }
    return stringField(errorRecord.message) || t("wa_referral_welcome_claim_failed");
  }

  async function applyPromo() {
    const code = get(state).promoCode.trim();
    if (!code) {
      setPromoFieldError(t("wa_promo_enter"));
      return;
    }
    state.update((s) => ({
      ...s,
      promoFieldError: "",
      promoBusy: true,
      promoStatus: "",
    }));
    try {
      const payload: PostPayload<"/api/promo/apply"> = { code };
      const response = await api("/promo/apply", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      const responsePayload = unwrap(response);
      state.update((s) => ({
        ...s,
        promoCode: "",
        promoStatus: responsePayload.end_date_text
          ? t("wa_promo_activated_until", { date: responsePayload.end_date_text })
          : t("wa_promo_activated"),
        promoIsError: false,
      }));
      await loadData({ fresh: true });
    } catch (error: unknown) {
      const message = stringField(asRecord(error).message) || t("wa_promo_activation_failed");
      state.update((s) => ({
        ...s,
        promoStatus: message,
        promoIsError: true,
        promoFieldError: message,
      }));
    } finally {
      state.update((s) => ({ ...s, promoBusy: false }));
    }
  }

  async function claimReferralWelcomeBonus() {
    try {
      const response = await api("/referral/welcome-bonus/claim", {
        method: "POST",
        body: JSON.stringify({} as PostPayload<"/api/referral/welcome-bonus/claim">),
      });
      const responsePayload = unwrap(response);
      showToast(
        responsePayload.end_date_text
          ? t("wa_referral_welcome_claimed_until", { date: responsePayload.end_date_text })
          : t("wa_referral_welcome_claimed")
      );
      await loadData({ fresh: true });
      await maybeShowActivationSuccessDialog({ source: "referral_welcome", force: true });
    } catch (error: unknown) {
      showToast(referralWelcomeFailureMessage(error));
    }
  }

  async function activateTrial() {
    if (get(state).trialBusy) return;
    state.update((s) => ({
      ...s,
      trialBusy: true,
      trialActivationResult: null,
      trialActivationError: "",
    }));
    try {
      const response = await api("/trial/activate", {
        method: "POST",
        body: JSON.stringify({} as PostPayload<"/api/trial/activate">),
      });
      const responsePayload = unwrap(response);
      state.update((s) => ({
        ...s,
        trialActivationResult: responsePayload,
      }));
      showToast(t("wa_trial_activated"));
      await loadData({ fresh: true });
      await maybeShowActivationSuccessDialog({ source: "trial", force: true });
    } catch (error: unknown) {
      const message = trialActivationFailureMessage(error);
      state.update((s) => ({ ...s, trialActivationError: message }));
      showToast(message);
    } finally {
      state.update((s) => ({ ...s, trialBusy: false }));
    }
  }

  return {
    subscribe: state.subscribe,
    set: state.set,
    update: state.update,
    setPromoCode,
    setPromoFieldError,
    clearPromoFieldError,
    applyPromo,
    claimReferralWelcomeBonus,
    activateTrial,
  };
}
