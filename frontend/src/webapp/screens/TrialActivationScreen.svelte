<script lang="ts">
  import {
    ArrowLeft,
    CheckCircle2,
    CircleX,
    Download,
    Gift,
    RefreshCw,
    Send,
  } from "$components/ui/icons.js";

  import BrandMark from "$lib/webapp/BrandMark.svelte";
  import { AttentionDot } from "$components/ui/index.js";
  import Button from "$components/ui/button.svelte";
  import Card from "$components/ui/card.svelte";
  import { formatTrafficGb } from "../../lib/webapp/formatters.js";

  type AnyRecord = Record<string, any>;
  type Translate = (key: string, params?: Record<string, unknown>, fallback?: string) => string;
  type VoidAction = () => void;
  type ActivateTrialFn = (botToken?: string) => void;

  type Props = {
    appSettings?: AnyRecord;
    brand?: AnyRecord;
    brandTitle?: string;
    subscription?: AnyRecord;
    trialBusy?: boolean;
    linkTelegramBusy?: boolean;
    trialResult?: AnyRecord | null;
    trialError?: string;
    activateTrial?: ActivateTrialFn;
    linkTelegramAndActivateTrial?: VoidAction;
    openInstallOrConnect?: VoidAction;
    goHome?: VoidAction;
    t?: Translate;
  };

  let {
    appSettings = {},
    brand = {},
    brandTitle = "",
    subscription = {},
    trialBusy = false,
    linkTelegramBusy = false,
    trialResult = null,
    trialError = "",
    activateTrial = () => {},
    linkTelegramAndActivateTrial = () => {},
    openInstallOrConnect = () => {},
    goHome = () => {},
    t = (key, _params = {}, fallback = "") => fallback || key,
  }: Props = $props();

  let requested = $state(false);
  let botTokenDraft = $state("");

  const trialEnabled = $derived(Boolean(appSettings?.trial_enabled));
  const trialAvailable = $derived(Boolean(appSettings?.trial_available));
  const trialRequiresTelegram = $derived(
    Boolean(trialEnabled && appSettings?.trial_requires_telegram && !subscription?.active)
  );
  const hermesMode = $derived(
    String(appSettings?.panel_write_mode || "").toLowerCase() === "hermes"
  );
  const isTrialStatus = $derived(
    Boolean(trialResult?.activated) ||
      String(subscription?.status || "")
        .toUpperCase()
        .includes("TRIAL")
  );
  const hasActiveAccess = $derived(Boolean(subscription?.active || trialResult?.activated));
  const hermesTokenRequired = $derived(Boolean(hermesMode && !hasActiveAccess));
  const canRequestTrial = $derived(
    Boolean(trialEnabled && trialAvailable && !subscription?.active)
  );
  const trimmedToken = $derived(botTokenDraft.trim());
  const canSubmit = $derived(canRequestTrial && (!hermesTokenRequired || trimmedToken.length > 0));
  const successTitle = $derived(
    isTrialStatus
      ? t("wa_trial_activated")
      : t("wa_home_subscription_active", {}, "Subscription active")
  );
  const endDateText = $derived(trialResult?.end_date_text || subscription?.end_date_text || "");
  const daysLeft = $derived(
    Number(trialResult?.days || subscription?.days_left || appSettings?.trial_duration_days || 0)
  );
  const trafficLabel = $derived(trialTrafficLabel());

  function trialTrafficLabel() {
    const resultTraffic = Number(trialResult?.traffic_gb || 0);
    const settingsTraffic = Number(appSettings?.trial_traffic_limit_gb || 0);
    const limit = resultTraffic || settingsTraffic;
    return limit > 0 ? formatTrafficGb(limit) : t("wa_unlimited_traffic");
  }

  function submitActivation() {
    if (requested || trialBusy || !canSubmit) return;
    requested = true;
    const token = hermesTokenRequired ? trimmedToken : "";
    activateTrial(token || undefined);
  }
</script>

<main class="trial-activation-screen">
  <div class="login-brand trial-activation-brand">
    <BrandMark {brand} size="lg" />
    <h1>{brandTitle}</h1>
  </div>

  <Card class="trial-activation-card">
    <div
      class={`trial-activation-icon ${
        trialBusy ? "trial-activation-icon-loading" : hasActiveAccess ? "is-success" : "is-muted"
      }`}
      aria-hidden="true"
    >
      {#if trialBusy}
        <RefreshCw size={27} />
      {:else if hasActiveAccess}
        <CheckCircle2 size={30} />
      {:else if trialRequiresTelegram}
        <Gift size={30} />
      {:else if trialError || !canRequestTrial}
        <CircleX size={30} />
      {:else}
        <Gift size={30} />
      {/if}
    </div>

    <div class="trial-activation-copy" aria-busy={trialBusy}>
      {#if trialBusy}
        <h2>{t("wa_trial_activation_loading", {}, "Activating trial...")}</h2>
        <p>{t("wa_trial_activation_wait", {}, "Preparing access and connection details.")}</p>
      {:else if hasActiveAccess}
        <h2>{successTitle}</h2>
        <p>
          {t(
            "wa_trial_active_hint",
            {},
            "Access is ready. Install the app and import the profile."
          )}
        </p>
        <dl class="trial-activation-facts">
          {#if endDateText}
            <div>
              <dt>{t("wa_trial_active_until_label", {}, "Active until")}</dt>
              <dd>{endDateText}</dd>
            </div>
          {/if}
          {#if daysLeft > 0}
            <div>
              <dt>{t("wa_trial_days_left_label", {}, "Time left")}</dt>
              <dd>{t("wa_trial_days_left", { days: daysLeft }, "{days} days")}</dd>
            </div>
          {/if}
          {#if !hermesMode}
            <div>
              <dt>{t("wa_trial_traffic_label", {}, "Traffic")}</dt>
              <dd>{trafficLabel}</dd>
            </div>
          {/if}
        </dl>
      {:else if trialRequiresTelegram}
        <h2>{t("wa_trial_telegram_required_title", {}, "Привяжите Telegram для триала")}</h2>
        <p>
          {t(
            "wa_trial_telegram_required_description",
            {
              duration:
                daysLeft > 0 ? t("wa_trial_days_left", { days: daysLeft }, "{days} days") : "",
              traffic: trafficLabel,
            },
            "Чтобы активировать пробный период, сначала привяжите Telegram."
          )}
        </p>
        <dl class="trial-activation-facts">
          {#if daysLeft > 0}
            <div>
              <dt>{t("wa_trial_duration_label", {}, "Срок")}</dt>
              <dd>{t("wa_trial_days_left", { days: daysLeft }, "{days} days")}</dd>
            </div>
          {/if}
          {#if !hermesMode}
            <div>
              <dt>{t("wa_trial_traffic_label", {}, "Traffic")}</dt>
              <dd>{trafficLabel}</dd>
            </div>
          {/if}
        </dl>
      {:else if trialError}
        <h2>{t("wa_trial_activation_failed")}</h2>
        <p>{trialError}</p>
      {:else if canRequestTrial && hermesTokenRequired}
        <h2>{t("wa_trial_token_required_title", {}, "Укажите токен бота")}</h2>
        <p>
          {t(
            "wa_trial_token_required_hint",
            {},
            "Создайте бота через @BotFather и вставьте сюда его токен. Бот будет принимать сообщения от ваших клиентов."
          )}
        </p>
        <details style="margin: 0 0 10px; font-size: 12px; color: var(--muted);">
          <summary style="cursor: pointer;">Как получить токен (пошагово)?</summary>
          <ol style="padding-left: 20px; margin: 6px 0 0;">
            <li>
              Откройте <a href="https://t.me/BotFather" target="_blank" rel="noopener">@BotFather</a
              > в Telegram
            </li>
            <li>Отправьте команду <code>/newbot</code></li>
            <li>Задайте имя и @username бота</li>
            <li>Скопируйте токен вида <code>123456789:ABCdef...</code></li>
            <li>Вставьте его в поле ниже</li>
          </ol>
        </details>
        <label class="trial-token-input">
          <span>{t("wa_trial_bot_token_label", {}, "BotFather token")}</span>
          <input
            type="text"
            inputmode="text"
            autocomplete="off"
            spellcheck="false"
            placeholder="123456789:ABCdef-…"
            bind:value={botTokenDraft}
          />
        </label>
      {:else}
        <h2>{t("wa_trial_unavailable_title", {}, "Trial is unavailable")}</h2>
        <p>
          {t(
            "wa_trial_unavailable_hint",
            {},
            "Trial may already be used, or this account already has active access."
          )}
        </p>
      {/if}
    </div>
  </Card>

  <div class="trial-activation-actions">
    {#if hasActiveAccess}
      <Button class="wide" onclick={openInstallOrConnect}>
        <Download size={18} />
        {t("wa_install_and_configure")}
      </Button>
    {:else if trialRequiresTelegram}
      <Button
        class="wide settings-telegram-link-btn attention-wrap"
        variant="telegram"
        onclick={linkTelegramAndActivateTrial}
        disabled={linkTelegramBusy || trialBusy}
      >
        <AttentionDot />
        <Send size={18} />
        {t("wa_trial_link_telegram_and_activate", {}, "Привязать и активировать")}
      </Button>
    {:else if canRequestTrial}
      <Button class="wide" onclick={submitActivation} disabled={!canSubmit || trialBusy}>
        <RefreshCw size={18} />
        {trialError
          ? t("wa_trial_retry", {}, "Try again")
          : hermesTokenRequired
            ? t("wa_trial_activate_with_token", {}, "Активировать")
            : hermesMode
              ? t("wa_trial_activate_hosting", {}, "Запустить пробный хостинг")
              : t("wa_trial_try_free", {}, "Попробовать бесплатно")}
      </Button>
    {/if}
    <Button class="wide" variant="secondary" onclick={goHome}>
      <ArrowLeft size={18} />
      {t("wa_nav_home", {}, "Home")}
    </Button>
  </div>
</main>

<style>
  .trial-activation-screen {
    display: grid;
    min-height: calc(100dvh - 34px);
    align-content: center;
    gap: 18px;
    padding-bottom: 86px;
    animation: section-enter 0.22s ease-out both;
  }

  .trial-activation-brand {
    gap: 8px;
  }

  .trial-activation-brand h1 {
    font-size: 25px;
  }

  :global(.card.trial-activation-card) {
    display: grid;
    justify-items: center;
    gap: 14px;
    background: color-mix(in srgb, var(--accent) 6%, var(--panel));
    padding: 20px 16px 18px;
    text-align: center;
  }

  .trial-activation-icon {
    display: grid;
    width: 58px;
    height: 58px;
    place-items: center;
    border: 1px solid var(--surface-subtle-border);
    border-radius: 50%;
    color: var(--muted);
    background: color-mix(in srgb, var(--panel) 70%, transparent);
  }

  .trial-activation-icon.is-success {
    border-color: color-mix(in srgb, var(--accent) 52%, var(--border));
    color: var(--accent);
    background: color-mix(in srgb, var(--accent) 13%, var(--panel));
  }

  :global(.trial-activation-icon-loading svg) {
    animation: trial-spin 0.8s linear infinite;
  }

  .trial-activation-copy {
    display: grid;
    gap: 8px;
    width: 100%;
  }

  .trial-activation-copy h2,
  .trial-activation-copy p {
    margin: 0;
  }

  .trial-activation-copy h2 {
    color: var(--text);
    font-size: 19px;
    font-weight: 900;
    line-height: 1.15;
  }

  .trial-activation-copy p {
    color: var(--muted);
    font-size: 13px;
    line-height: 1.42;
  }

  .trial-activation-facts {
    display: grid;
    gap: 8px;
    width: 100%;
    margin: 8px 0 0;
  }

  .trial-activation-facts div {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    min-width: 0;
    padding: 9px 10px;
    border: 1px solid var(--surface-subtle-border);
    border-radius: 12px;
    background: var(--surface-subtle);
    text-align: left;
  }

  .trial-activation-facts dt,
  .trial-activation-facts dd {
    min-width: 0;
    margin: 0;
    font-size: 12px;
    line-height: 1.2;
  }

  .trial-activation-facts dt {
    color: var(--muted);
  }

  .trial-activation-facts dd {
    overflow-wrap: anywhere;
    color: var(--text);
    font-weight: 850;
    text-align: right;
  }

  .trial-activation-actions {
    display: grid;
    gap: 10px;
  }

  @keyframes trial-spin {
    to {
      transform: rotate(360deg);
    }
  }

  .trial-token-input {
    display: grid;
    gap: 6px;
    width: 100%;
    margin-top: 6px;
    text-align: left;
  }

  .trial-token-input span {
    font-size: 12px;
    color: var(--muted);
  }

  .trial-token-input input {
    width: 100%;
    padding: 10px 12px;
    border-radius: 10px;
    border: 1px solid var(--surface-subtle-border);
    background: var(--surface-subtle);
    color: var(--text);
    font-family: ui-monospace, SFMono-Regular, monospace;
    font-size: 13px;
    line-height: 1.3;
  }

  .trial-token-input input:focus {
    outline: 2px solid color-mix(in srgb, var(--accent) 60%, transparent);
    outline-offset: 1px;
  }
</style>
