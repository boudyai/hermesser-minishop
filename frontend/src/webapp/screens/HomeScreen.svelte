<script lang="ts">
  import { onMount } from "svelte";
  import {
    CheckCircle2,
    CircleQuestionMark,
    CircleX,
    CreditCard,
    Database,
    Download,
    Gift,
    Repeat2,
    Send,
  } from "$components/ui/icons.js";

  import BrandMark from "$lib/webapp/BrandMark.svelte";
  import { AttentionDot } from "$components/ui/index.js";
  import Button from "$components/ui/button.svelte";
  import Card from "$components/ui/card.svelte";
  import BotStatusCard from "../components/BotStatusCard.svelte";
  import CornllmTopupCard from "../components/CornllmTopupCard.svelte";
  import OnboardingWizard from "../components/OnboardingWizard.svelte";
  import TelegramNotificationsBanner from "../TelegramNotificationsBanner.svelte";
  import { LinearProgress } from "$components/patterns/webapp/index.js";
  import { formatTrafficGb } from "../../lib/webapp/formatters.js";
  import {
    trafficPercent as trafficPercentFn,
    trafficLabel as trafficLabelFn,
    trafficResetLabel as trafficResetLabelFn,
    regularTrafficLimitVisible as regularTrafficLimitVisibleFn,
    premiumTrafficPercent as premiumTrafficPercentFn,
    premiumTrafficLabel as premiumTrafficLabelFn,
    premiumTrafficLimitVisible as premiumTrafficLimitVisibleFn,
    premiumTitle as premiumTitleFn,
    premiumServerLabels as premiumServerLabelsFn,
    activeSubscriptionTermLabel as activeSubscriptionTermLabelFn,
  } from "../../lib/webapp/traffic.js";

  const SUBSCRIPTION_EXPIRY_WARNING_MS = 72 * 60 * 60 * 1000;
  const SUBSCRIPTION_EXPIRING_SOON_MS = 24 * 60 * 60 * 1000;

  type AnyRecord = Record<string, any>;
  type ApiUnchecked = (
    path: string,
    options?: Parameters<typeof fetch>[1]
  ) => Promise<Record<string, unknown>>;
  type Translate = (key: string, params?: Record<string, unknown>, fallback?: string) => string;

  let {
    appSettings = {},
    apiUnchecked,
    brand = {},
    brandTitle = "",
    canChangeTariff = false,
    premiumTrafficTopupBarClickable = false,
    premiumTrafficTopupUnlocked = false,
    regularTrafficTopupBarClickable = false,
    regularTrafficTopupUnlocked = false,
    referral = {},
    currentTariffName = "",
    hasActiveTariffSubscription = false,
    hasMultipleTariffs = false,
    methods = [],
    subscription = {},
    autoRenewBusy = false,
    linkTelegramBusy = false,
    telegramNotificationsNeedPrompt = false,
    telegramNotificationsStartLink = "",
    telegramNotificationsStatus = "unknown",
    trafficMode = false,
    trialBusy = false,
    termUnitLabel = () => "",
    activateTrial = () => {},
    toggleAutoRenew = () => {},
    linkTelegramAndActivateTrial = () => {},
    linkTelegramAndClaimReferralWelcome = () => {},
    openConnectLink = () => {},
    openPaymentModal = () => {},
    openTelegramNotificationsBot = () => {},
    openRegularTopupModal = () => {},
    openPremiumTopupModal = () => {},
    openTariffChangeModal = () => {},
    goTrial = () => {},
    primaryPayActionLabel = () => "",
    t = (key) => key,
  }: {
    appSettings?: AnyRecord;
    apiUnchecked?: ApiUnchecked;
    brand?: AnyRecord;
    brandTitle?: string;
    canChangeTariff?: boolean;
    premiumTrafficTopupBarClickable?: boolean;
    premiumTrafficTopupUnlocked?: boolean;
    regularTrafficTopupBarClickable?: boolean;
    regularTrafficTopupUnlocked?: boolean;
    referral?: AnyRecord;
    currentTariffName?: string;
    hasActiveTariffSubscription?: boolean;
    hasMultipleTariffs?: boolean;
    methods?: AnyRecord[];
    subscription?: AnyRecord;
    autoRenewBusy?: boolean;
    linkTelegramBusy?: boolean;
    telegramNotificationsNeedPrompt?: boolean;
    telegramNotificationsStartLink?: string;
    telegramNotificationsStatus?: string;
    trafficMode?: boolean;
    trialBusy?: boolean;
    termUnitLabel?: (value: number, unit: string) => string;
    activateTrial?: () => void;
    toggleAutoRenew?: (enabled: boolean) => void;
    linkTelegramAndActivateTrial?: () => void;
    linkTelegramAndClaimReferralWelcome?: () => void;
    openConnectLink?: () => void;
    openPaymentModal?: () => void;
    openTelegramNotificationsBot?: () => void;
    openRegularTopupModal?: () => void;
    openPremiumTopupModal?: () => void;
    openTariffChangeModal?: () => void;
    goTrial?: () => void;
    primaryPayActionLabel?: () => string;
    t?: Translate;
  } = $props();

  let nowMs = $state(Date.now());

  const hermesMode = $derived(
    String(appSettings?.panel_write_mode || "").toLowerCase() === "hermes"
  );
  const hasBotToken = $derived(Boolean(appSettings?.has_bot_token));
  const hermesTokenRequired = $derived(Boolean(hermesMode && !hasBotToken));
  // ponytail: Telegram Mini App webview silently swallows window.open
  // for arbitrary URLs, so "Open bot" needs to go through the SDK's
  // openTelegramLink (which appends the right ?tgsr query and is the
  // only path Telegram actually honors on iOS). Fall back to a plain
  // window.open for non-Telegram URLs and for non-Mini-App sessions
  // where the SDK isn't injected yet.
  function openBotChat(url: string): void {
    if (typeof window === "undefined" || !url) return;
    const tg = (window as AnyRecord).Telegram as
      | { WebApp?: { openTelegramLink?: (u: string) => void; openLink?: (u: string) => void } }
      | undefined;
    const sdk = tg?.WebApp;
    if (sdk?.openTelegramLink && /^https:\/\/t\.me\//i.test(url)) {
      try {
        sdk.openTelegramLink(url);
        return;
      } catch {
        // fall through to plain window.open below
      }
    }
    try {
      window.open(url, "_blank", "noopener,noreferrer");
    } catch {
      // some webviews reject window.open entirely — last-ditch: location.assign
      if (typeof window !== "undefined") window.location.assign(url);
    }
  }
  // ponytail: in hermes mode the InstallGuideScreen has no proxy
  // config links to show, so "Открыть бота" should open the bot's
  // Telegram chat directly instead of rendering an empty page.
  const hermesBotUsername = $derived(
    String(subscription?.bot_username || appSettings?.bot_username || "").trim()
  );
  const hermesTMeUrl = $derived(hermesBotUsername ? `https://t.me/${hermesBotUsername}` : "");
  // ponytail: track tenant lifecycle to show a "Bot deleted" card
  // with a re-create action. tenant_status comes from
  // _tenant_runtime_fields via the /api/me serializer.
  const hermesTenantStatus = $derived(
    String(subscription?.tenant_status || subscription?.status || "").toLowerCase()
  );
  const hermesBotDeleted = $derived(
    hermesMode && ["deleting", "deleted", "archived"].includes(hermesTenantStatus)
  );
  let hermesCardBusy = $state(false);
  let hermesCardError = $state<string | null>(null);
  async function recreateHermesBot() {
    if (hermesCardBusy) return;
    hermesCardBusy = true;
    hermesCardError = null;
    try {
      // ponytail: the user has an active local subscription
      // already, so /api/trial/activate returns 400 with
      // "trial_already_had_subscription_or_trial". Use the
      // dedicated re-create endpoint which re-runs
      // create_panel_user with the stored bot_token — the
      // provisioning-core resurrects the existing tenant row
      // in place and enqueues fresh create_litellm_key +
      // create_vm jobs.
      const result = await apiUnchecked("/tenant/recreate", {
        method: "POST",
      });
      if (!result || result.ok === false) {
        hermesCardError = t(
          "wa_hermes_bot_action_recreate_failed",
          {},
          "Failed to create. Try again or contact support."
        );
      } else {
        setTimeout(() => window.location.reload(), 1500);
      }
    } catch (_e) {
      hermesCardError = t(
        "wa_hermes_bot_action_recreate_failed",
        {},
        "Failed to create. Try again or contact support."
      );
    } finally {
      hermesCardBusy = false;
    }
  }
  function openHermesBotChat() {
    if (!hermesTMeUrl) return;
    openBotChat(hermesTMeUrl);
  }
  // ponytail: in hermes mode the InstallGuideScreen has no proxy
  // config links to show, so the main CTA opens the bot's Telegram
  // chat directly. Falls back to the proxy install-guide flow when
  // the bot username is not yet known.
  function onPrimaryOpenBot() {
    if (hermesMode && hermesTMeUrl) {
      openHermesBotChat();
      return;
    }
    openConnectLink();
  }
  function trafficPercent(sub: AnyRecord) {
    return trafficPercentFn(sub);
  }
  function activeStatusTitle() {
    if (hermesMode) return t("wa_home_bot_active", {}, "Bot is active");
    return trafficMode ? t("wa_home_access_active") : t("wa_home_subscription_active");
  }
  function installButtonTitle() {
    return hermesMode ? t("wa_open_bot", {}, "Open bot") : t("wa_install_and_configure");
  }
  function trafficLabel(sub: AnyRecord) {
    return trafficLabelFn(sub, t);
  }
  function trafficResetLabel(sub: AnyRecord) {
    return trafficResetLabelFn(sub, t);
  }
  function regularTrafficLimitVisible(sub: AnyRecord = subscription) {
    return regularTrafficLimitVisibleFn(sub);
  }
  function regularTrafficDepleted(sub: AnyRecord = subscription) {
    const used = Number(sub?.traffic_used_bytes || 0);
    const limit = Number(sub?.traffic_limit_bytes || 0);
    return limit > 0 && used >= limit;
  }
  function regularTrafficCardClass(sub: AnyRecord = subscription) {
    return [
      "traffic-card-compact",
      regularTrafficTopupBarClickable ? "traffic-card-clickable" : "",
      regularTrafficDepleted(sub) ? "traffic-card-depleted" : "",
    ]
      .filter(Boolean)
      .join(" ");
  }
  function regularTrafficMetaLabel(sub: AnyRecord = subscription) {
    return regularTrafficDepleted(sub) ? t("wa_traffic_depleted") : trafficResetLabel(sub);
  }
  function premiumTrafficAvailable(sub: AnyRecord = subscription) {
    return !regularTrafficDepleted(sub);
  }
  function premiumTrafficPercent(sub: AnyRecord) {
    return premiumTrafficPercentFn(sub);
  }
  function premiumTrafficLimitVisible(sub: AnyRecord = subscription) {
    return premiumTrafficLimitVisibleFn(sub);
  }
  function premiumTrafficLabel(sub: AnyRecord) {
    return premiumTrafficLabelFn(sub, t);
  }
  function premiumTitle(sub: AnyRecord = subscription) {
    return premiumTitleFn(sub, t);
  }
  function premiumTrafficMetaLabel(sub: AnyRecord = subscription) {
    return sub?.premium_is_limited
      ? t("wa_premium_access_limited", {}, "Premium access temporarily limited")
      : t("wa_premium_reset_monthly", {}, "Separate monthly limit");
  }
  function premiumServerLabels(sub: AnyRecord) {
    return premiumServerLabelsFn(sub);
  }
  function activeSubscriptionTermLabel(sub: AnyRecord) {
    return activeSubscriptionTermLabelFn(sub, { t, termUnitLabel });
  }
  function trialTrafficLabel() {
    const limit = Number(appSettings?.trial_traffic_limit_gb || 0);
    return limit > 0 ? formatTrafficGb(limit) : t("wa_unlimited_traffic");
  }
  function trialDurationLabel() {
    const days = Number(appSettings?.trial_duration_days || 0);
    return t("wa_sub_term_value_unit", {
      value: days,
      unit: termUnitLabel(days, "day"),
    });
  }
  function parseSubscriptionEndMs(sub: AnyRecord) {
    const raw = String(sub?.end_date || "").trim();
    if (!raw) return null;
    const parsed = Date.parse(raw);
    return Number.isFinite(parsed) ? parsed : null;
  }
  function dateOnlyFromEndText(text: unknown) {
    const value = String(text || "").trim();
    if (!value) return "";
    return value.split(/\s+/)[0] || value;
  }
  function dateOnlyFromIso(text: unknown) {
    const match = String(text || "").match(/^(\d{4})-(\d{2})-(\d{2})/);
    return match ? `${match[3]}.${match[2]}.${match[1]}` : "";
  }
  function subscriptionEndDateLabel(sub: AnyRecord) {
    return dateOnlyFromEndText(sub?.end_date_text) || dateOnlyFromIso(sub?.end_date);
  }
  function formatSubscriptionCountdown(ms: number) {
    const totalSeconds = Math.max(0, Math.floor(ms / 1000));
    const hours = Math.floor(totalSeconds / 3600);
    const minutes = Math.floor((totalSeconds % 3600) / 60);
    const seconds = totalSeconds % 60;
    const pad = (value: number) => String(value).padStart(2, "0");
    return `${pad(hours)}:${pad(minutes)}:${pad(seconds)}`;
  }

  const trialOfferAvailable = $derived(
    Boolean(!subscription?.active && appSettings?.trial_enabled && appSettings?.trial_available)
  );
  const trialRequiresTelegram = $derived(
    Boolean(
      !subscription?.active && appSettings?.trial_enabled && appSettings?.trial_requires_telegram
    )
  );
  const referralWelcomeRequiresTelegram = $derived(
    Boolean(
      !subscription?.active &&
      referral?.welcome_bonus_requires_telegram &&
      Number(referral?.welcome_bonus_days || 0) > 0
    )
  );
  const subscriptionEndMs = $derived(
    subscription?.active ? parseSubscriptionEndMs(subscription) : null
  );
  const subscriptionRemainingMs = $derived(Math.max(0, Number(subscriptionEndMs || 0) - nowMs));
  const subscriptionExpiryWarning = $derived(
    Boolean(
      subscription?.active &&
      subscriptionEndMs &&
      subscriptionRemainingMs > 0 &&
      subscriptionRemainingMs <= SUBSCRIPTION_EXPIRY_WARNING_MS
    )
  );
  const subscriptionEndDateText = $derived(subscriptionEndDateLabel(subscription));
  const subscriptionEndCountdown = $derived(formatSubscriptionCountdown(subscriptionRemainingMs));
  const subscriptionEndCountdownLabel = $derived(
    t(
      "wa_subscription_remaining_countdown",
      { countdown: subscriptionEndCountdown },
      `осталось: ${subscriptionEndCountdown}`
    )
  );
  const subscriptionExpiringSoon = $derived(
    Boolean(
      subscription?.active &&
      subscriptionEndMs &&
      subscriptionRemainingMs > 0 &&
      subscriptionRemainingMs < SUBSCRIPTION_EXPIRING_SOON_MS
    )
  );
  const subscriptionTermDisplayText = $derived(
    subscriptionExpiringSoon
      ? t("wa_subscription_expiring_soon", {}, "Expiring soon!")
      : activeSubscriptionTermLabel(subscription)
  );
  const subscriptionEndDisplayText = $derived(
    subscriptionExpiryWarning
      ? `${subscriptionEndDateText || subscription.end_date_text} \u00b7 ${subscriptionEndCountdownLabel}`
      : subscriptionEndDateText
  );
  const statusCardClass = $derived(
    [
      "status-card",
      subscription.active ? "" : "status-card-inactive",
      subscriptionExpiryWarning ? "status-card-warning" : "",
    ]
      .filter(Boolean)
      .join(" ")
  );
  const autoRenewVisible = $derived(
    Boolean(subscription?.active && subscription?.auto_renew_available)
  );
  const autoRenewEnabled = $derived(Boolean(subscription?.auto_renew_enabled));

  onMount(() => {
    const countdownTimer = window.setInterval(() => {
      if (subscription?.active) nowMs = Date.now();
    }, 1000);

    return () => window.clearInterval(countdownTimer);
  });
</script>

<main class="home-layout">
  <div class="login-brand home-brand">
    <BrandMark {brand} size="xl" />
    <h1>{brandTitle}</h1>
  </div>

  {#if telegramNotificationsNeedPrompt}
    <TelegramNotificationsBanner
      startLink={telegramNotificationsStartLink}
      status={telegramNotificationsStatus}
      onOpenBot={openTelegramNotificationsBot}
      {t}
    />
  {/if}

  <div class="home-bottom">
    <Card class={statusCardClass}>
      {#if subscription.active}
        <div class="sub-status">
          <CheckCircle2 class="sub-status-icon" size={23} />
          <div class="sub-status-main">
            <h2>
              {activeStatusTitle()} | {subscriptionTermDisplayText}
            </h2>
            <div
              class:sub-status-details-with-tariff={hasActiveTariffSubscription &&
                hasMultipleTariffs &&
                currentTariffName}
              class="sub-status-details"
            >
              {#if hasActiveTariffSubscription && hasMultipleTariffs && currentTariffName}
                <p class="current-tariff-line">
                  {t("wa_current_tariff", { tariff: currentTariffName })}
                </p>
              {/if}
              <p class="subscription-end-line">
                {subscriptionEndDisplayText
                  ? t("wa_until_date", { date: subscriptionEndDisplayText })
                  : subscription.remaining_text}
              </p>
            </div>
          </div>
          {#if canChangeTariff}
            <Button
              data-webapp-action="open-tariff-change"
              class="status-tariff-action"
              variant="secondary"
              onclick={openTariffChangeModal}
            >
              <Repeat2 size={17} />
              {t("wa_change_tariff")}
            </Button>
          {/if}
        </div>
        {#if autoRenewVisible}
          <div class="auto-renew-row">
            <div class="auto-renew-state">
              <Repeat2 size={17} />
              <span>
                <strong>
                  {autoRenewEnabled ? t("wa_auto_renew_enabled") : t("wa_auto_renew_disabled")}
                </strong>
              </span>
            </div>
            <Button
              class="auto-renew-action"
              variant="secondary"
              onclick={() => toggleAutoRenew(!autoRenewEnabled)}
              disabled={autoRenewBusy ||
                (!autoRenewEnabled && !subscription?.auto_renew_can_enable)}
            >
              {#if autoRenewEnabled}
                <CircleX size={17} />
                {t("wa_auto_renew_disable")}
              {:else}
                <Repeat2 size={17} />
                {t("wa_auto_renew_enable")}
              {/if}
            </Button>
          </div>
        {/if}
      {:else}
        <div class="sub-status sub-status-inactive">
          <CircleX class="sub-status-icon" size={23} />
          <h2>{t("wa_home_subscription_inactive")}</h2>
        </div>
      {/if}
    </Card>

    {#if subscription.active && hermesMode && hermesBotDeleted}
      <Card class="trial-card">
        <h2 style="margin: 0 0 8px; font-size: 15px;">
          {t(
            "wa_hermes_bot_card_deleted",
            {},
            "🤖 Бот удалён\nЧтобы создать нового, нажмите кнопку ниже."
          )}
        </h2>
        <Button class="wide" onclick={recreateHermesBot} disabled={hermesCardBusy}>
          {t("wa_hermes_bot_action_create", {}, "🆕 Create new bot")}
        </Button>
        {#if hermesCardError}
          <p style="margin: 8px 0 0; color: var(--danger); font-size: 12px;">
            {hermesCardError}
          </p>
        {/if}
      </Card>
    {/if}

    {#if subscription.active && hermesMode}
      <BotStatusCard {subscription} {appSettings} {apiUnchecked} {t} />
      <CornllmTopupCard {subscription} {appSettings} {apiUnchecked} {methods} {t} />
    {/if}

    {#if !subscription.active && hermesMode}
      <OnboardingWizard
        {appSettings}
        {subscription}
        {apiUnchecked}
        {methods}
        {t}
        {hasActiveTariffSubscription}
        {hasMultipleTariffs}
        {currentTariffName}
        {openPaymentModal}
      />
    {/if}

    {#if subscription.active}
      {#if regularTrafficLimitVisible(subscription)}
        <Card compact class={regularTrafficCardClass(subscription)}>
          {#if regularTrafficTopupBarClickable}
            <button
              data-webapp-action="open-regular-topup"
              class="card-click-target"
              type="button"
              onclick={openRegularTopupModal}
              aria-label={t("wa_add_traffic")}
            ></button>
          {/if}
          <div class="traffic-summary-row">
            <span class="traffic-summary-left">
              {t("wa_home_traffic_used")}
              <span class="traffic-summary-separator" aria-hidden="true">|</span>
              {regularTrafficMetaLabel(subscription)}
            </span>
            <strong class="traffic-summary-right">
              <span>{trafficLabel(subscription)}</span>
              <span class="traffic-summary-separator" aria-hidden="true">|</span>
              <span>{trafficPercent(subscription)}%</span>
            </strong>
          </div>
          <LinearProgress value={trafficPercent(subscription)} label={t("wa_home_traffic_used")} />
        </Card>
      {/if}
      {#if premiumTrafficAvailable(subscription) && premiumTrafficLimitVisible(subscription)}
        <Card
          compact
          class={`traffic-card-compact ${premiumTrafficTopupBarClickable ? "traffic-card-clickable " : ""}premium-traffic-card${subscription?.premium_is_limited ? " premium-traffic-card-limited" : ""}`}
        >
          {#if premiumTrafficTopupBarClickable}
            <button
              data-webapp-action="open-premium-topup"
              class="card-click-target"
              type="button"
              onclick={openPremiumTopupModal}
              aria-label={t("wa_add_traffic_premium", { target: premiumTitle(subscription) })}
            ></button>
          {/if}
          {#if premiumServerLabels(subscription).length}
            <details class="premium-server-dropdown premium-server-dropdown-inline">
              <summary class="traffic-summary-row premium-server-summary">
                <span class="traffic-summary-left premium-summary-trigger">
                  <span class="premium-summary-copy">
                    {premiumTitle(subscription)}
                    <span class="traffic-summary-separator" aria-hidden="true">|</span>
                    {premiumTrafficMetaLabel(subscription)}
                  </span>
                  <CircleQuestionMark class="premium-server-help-icon" size={15} />
                </span>
                <strong class="traffic-summary-right">
                  <span>{premiumTrafficLabel(subscription)}</span>
                  <span class="traffic-summary-separator" aria-hidden="true">|</span>
                  <span>{premiumTrafficPercent(subscription)}%</span>
                </strong>
              </summary>
              <div class="premium-server-list premium-server-list-dropdown">
                <div>
                  {#each premiumServerLabels(subscription).slice(0, 8) as label}
                    <span>{label}</span>
                  {/each}
                </div>
              </div>
            </details>
          {:else}
            <div class="traffic-summary-row">
              <span class="traffic-summary-left">
                {premiumTitle(subscription)}
                <span class="traffic-summary-separator" aria-hidden="true">|</span>
                {premiumTrafficMetaLabel(subscription)}
              </span>
              <strong class="traffic-summary-right">
                <span>{premiumTrafficLabel(subscription)}</span>
                <span class="traffic-summary-separator" aria-hidden="true">|</span>
                <span>{premiumTrafficPercent(subscription)}%</span>
              </strong>
            </div>
          {/if}
          <LinearProgress
            class="premium-progress"
            value={premiumTrafficPercent(subscription)}
            label={premiumTitle(subscription)}
          />
        </Card>
      {/if}
    {:else}
      {#if hermesTokenRequired}
        <Card class="trial-card">
          <div class="trial-card-head">
            <Gift size={22} />
            <span>
              <strong>
                {t("wa_home_set_token_first_title", {}, "Set the bot token")}
              </strong>
              <small>
                {t(
                  "wa_home_set_token_first_hint",
                  {},
                  "Go to Settings → Bot token and paste a token from @BotFather"
                )}
              </small>
            </span>
          </div>
        </Card>
      {/if}
      {#if referralWelcomeRequiresTelegram}
        <Card class="trial-card trial-offer-card">
          <div class="trial-card-head">
            <Gift size={22} />
            <span>
              <strong>
                {t(
                  "wa_referral_welcome_telegram_required_title",
                  {},
                  "Bonus awaits linking Telegram"
                )}
              </strong>
              <small>{t("wa_referral_program_title", {}, "Referral program")}</small>
            </span>
          </div>
          <p class="trial-card-description">
            {t(
              "wa_referral_welcome_telegram_required_description",
              { days: Number(referral?.welcome_bonus_days || 0) },
              "Link Telegram to claim {days} bonus days for signing up via invitation."
            )}
          </p>
          <Button
            class="wide trial-card-action settings-telegram-link-btn attention-wrap"
            variant="telegram"
            onclick={linkTelegramAndClaimReferralWelcome}
            disabled={linkTelegramBusy}
          >
            <AttentionDot />
            <Send size={18} />
            {t("wa_referral_link_telegram_and_claim", {}, "Link and claim bonus")}
          </Button>
        </Card>
      {/if}

      {#if trialOfferAvailable}
        <Card class="trial-card trial-offer-card">
          <div class="trial-card-head">
            <Gift size={22} />
            <span>
              <strong>{t("wa_trial_offer_title", {}, "Start with a free trial")}</strong>
              <small>{t("wa_trial_title")}</small>
            </span>
          </div>
          <p class="trial-card-description">
            {hermesMode
              ? t(
                  "wa_trial_offer_description_hermes",
                  { duration: trialDurationLabel() },
                  "Activate the trial: {duration} of free hosting for your Telegram bot with Hermes Agent."
                )
              : t(
                  "wa_trial_offer_description",
                  { duration: trialDurationLabel(), traffic: trialTrafficLabel() },
                  "Activate the trial: {duration} of access plus {traffic} download allowance, no payment needed."
                )}
          </p>
          <div class="trial-card-facts">
            <span>
              <small>{t("wa_trial_duration_label", {}, "Duration")}</small>
              <strong>{trialDurationLabel()}</strong>
            </span>
            {#if !hermesMode}
              <span>
                <small>{t("wa_trial_download_traffic_label", {}, "Download allowance")}</small>
                <strong>{trialTrafficLabel()}</strong>
              </span>
            {/if}
          </div>
          <Button
            class="wide trial-card-action"
            onclick={() => {
              if (hermesMode && !hasBotToken) {
                goTrial();
              } else {
                activateTrial();
              }
            }}
            disabled={trialBusy}
          >
            <Gift size={18} />
            {hermesMode
              ? t("wa_trial_activate_hosting", {}, "Start trial hosting")
              : t("wa_trial_try_free", {}, "Попробовать бесплатно")}
          </Button>
        </Card>
      {:else if trialRequiresTelegram}
        <Card class="trial-card trial-offer-card">
          <div class="trial-card-head">
            <Gift size={22} />
            <span>
              <strong>
                {t("wa_trial_telegram_required_title", {}, "Link Telegram to start the trial")}
              </strong>
              <small>{t("wa_trial_title")}</small>
            </span>
          </div>
          <p class="trial-card-description">
            {t(
              "wa_trial_telegram_required_description",
              { duration: trialDurationLabel(), traffic: trialTrafficLabel() },
              "To activate the {duration} trial with {traffic} allowance, first link your Telegram."
            )}
          </p>
          <div class="trial-card-facts">
            <span>
              <small>{t("wa_trial_duration_label", {}, "Duration")}</small>
              <strong>{trialDurationLabel()}</strong>
            </span>
            <span>
              <small>{t("wa_trial_download_traffic_label", {}, "Download allowance")}</small>
              <strong>{trialTrafficLabel()}</strong>
            </span>
          </div>
          <Button
            class="wide trial-card-action settings-telegram-link-btn attention-wrap"
            variant="telegram"
            onclick={linkTelegramAndActivateTrial}
            disabled={linkTelegramBusy || trialBusy}
          >
            <AttentionDot />
            <Send size={18} />
            {t("wa_trial_link_telegram_and_activate", {}, "Link and activate")}
          </Button>
        </Card>
      {/if}
    {/if}

    <div class="action-stack">
      {#if subscription.active}
        <Button
          class="wide"
          onclick={onPrimaryOpenBot}
          disabled={hermesMode && !hermesTMeUrl}
          title={hermesMode && !hermesTMeUrl
            ? t(
                "wa_hermes_open_bot_no_username",
                {},
                "Bot username is not yet known — wait for the container to start or contact support."
              )
            : undefined}
        >
          {#if hermesMode}
            <Send size={18} />
          {:else}
            <Download size={18} />
          {/if}
          {installButtonTitle()}
        </Button>
      {/if}
      <Button
        data-webapp-action="open-payment"
        class={`wide${subscription.active ? " subscription-renew-action" : ""}`}
        variant={subscription.active ? "secondary" : "default"}
        onclick={openPaymentModal}
      >
        {#if subscription.active}
          <CreditCard size={18} />
        {:else if trafficMode}
          <Database size={18} />
        {/if}
        {primaryPayActionLabel()}
      </Button>
      {#if regularTrafficTopupUnlocked && regularTrafficLimitVisible(subscription)}
        <Button
          data-webapp-action="open-regular-topup"
          class="wide"
          variant="secondary"
          onclick={openRegularTopupModal}
        >
          <Database size={18} />
          {t("wa_add_traffic")}
        </Button>
      {/if}
      {#if premiumTrafficTopupUnlocked && premiumTrafficAvailable(subscription) && premiumTrafficLimitVisible(subscription)}
        <Button
          data-webapp-action="open-premium-topup"
          class="wide"
          variant="secondary"
          onclick={openPremiumTopupModal}
        >
          <Database size={18} />
          {t("wa_add_traffic_premium", { target: premiumTitle(subscription) })}
        </Button>
      {/if}
    </div>
  </div>
</main>
