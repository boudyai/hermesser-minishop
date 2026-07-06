<script lang="ts">
  import { Check, ChevronRight, Server, Sparkles } from "$components/ui/icons.js";
  import Button from "$components/ui/button.svelte";
  import Card from "$components/ui/card.svelte";

  type AnyRecord = Record<string, any>;
  type ApiUnchecked = (
    path: string,
    options?: Parameters<typeof fetch>[1]
  ) => Promise<Record<string, unknown>>;

  let {
    appSettings = {},
    subscription = {},
    apiUnchecked,
    currentTariffName = "",
    hasMultipleTariffs = false,
    methods = [],
    hasActiveTariffSubscription = false,
    openPaymentModal = () => {},
    t = (key: string, _params?: AnyRecord, fallback?: string) => fallback || key,
  }: {
    appSettings?: AnyRecord;
    subscription?: AnyRecord;
    apiUnchecked?: ApiUnchecked;
    currentTariffName?: string;
    hasMultipleTariffs?: boolean;
    methods?: AnyRecord[];
    hasActiveTariffSubscription?: boolean;
    openPaymentModal?: (tariffKey?: string) => void;
    t?: (key: string, params?: AnyRecord, fallback?: string) => string;
  } = $props();

  const hermesMode = $derived(String(appSettings?.panel_write_mode || "") === "hermes");
  const hasBotToken = $derived(Boolean(appSettings?.has_bot_token));
  const active = $derived(Boolean(subscription?.active));
  const tenantStatus = $derived(String(subscription?.tenant_status || "").trim() || null);

  // ponytail: hosting tariffs live in tariffs.json (data/tariffs.json).
  // We hardcode the display here so the wizard works before the
  // tariff catalog loads and so we don't depend on the webapp's
  // enabled-tariff enumeration. Both plans map 1:1 to a
  // tariff_key the payment modal accepts.
  type HostingPlan = {
    key: "hosting_basic" | "hosting_plus";
    titleKey: string;
    titleFallback: string;
    priceRub: number;
    cpuCores: number;
    memoryGb: number;
    cornllmRubMonthly: number;
    bulletsKey: string;
    bulletsFallback: string;
  };
  const hostingPlans: HostingPlan[] = [
    {
      key: "hosting_basic",
      titleKey: "wa_hermes_tariff_basic",
      titleFallback: "Basic",
      priceRub: 300,
      cpuCores: 2,
      memoryGb: 4,
      cornllmRubMonthly: 0,
      bulletsKey: "wa_hermes_tariff_basic_bullets",
      bulletsFallback:
        "2 vCPU · 4 GB RAM · no included CornLLM balance (top up separately)",
    },
    {
      key: "hosting_plus",
      titleKey: "wa_hermes_tariff_plus",
      titleFallback: "Plus",
      priceRub: 500,
      cpuCores: 2,
      memoryGb: 4,
      cornllmRubMonthly: 300,
      bulletsKey: "wa_hermes_tariff_plus_bullets",
      bulletsFallback:
        "2 vCPU · 4 GB RAM · 300 ₽ CornLLM balance included every month",
    },
  ];

  let step = $state(1);
  let selectedPlan = $state<HostingPlan>(hostingPlans[1]);
  let botToken = $state("");
  let tokenBusy = $state(false);
  let tokenError = $state<string | null>(null);
  let tokenOk = $state(false);

  async function saveToken() {
    if (!botToken.trim() || !apiUnchecked) return;
    tokenBusy = true;
    tokenError = null;
    try {
      await apiUnchecked("/account/bot_token", {
        method: "PUT",
        body: JSON.stringify({ bot_token: botToken.trim() }),
      });
      tokenOk = true;
      step = 5;
    } catch (e) {
      tokenError = e instanceof Error ? e.message : "token_save_failed";
    } finally {
      tokenBusy = false;
    }
  }

  function payWithPlan() {
    if (methods.length === 0) return;
    openPaymentModal(selectedPlan.key);
  }

  // ponytail: Telegram Mini App webview silently swallows window.open
  // for arbitrary URLs on iOS. The "Open bot" CTA in the success
  // card has to go through the SDK's openTelegramLink, otherwise the
  // user sees the bot row but tapping it does nothing.
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
      if (typeof window !== "undefined") window.location.assign(url);
    }
  }
</script>

{#if hermesMode && !active}
  <Card class="onboarding-hero">
    <h2 style="margin: 0 0 6px; font-size: 18px;">
      {t("wa_hermes_onboarding_title", {}, "Launch your personal AI agent on Telegram")}
    </h2>
    <p style="margin: 0 0 12px; color: var(--muted); font-size: 13px;">
      {t(
        "wa_hermes_onboarding_subtitle",
        {},
        "Personal Hermes Agent on Telegram, running 24/7 on our server."
      )}
    </p>
    <ul style="margin: 0 0 14px; padding: 0; list-style: none; font-size: 13px;">
      <li style="display: flex; gap: 8px; align-items: flex-start; margin-bottom: 6px;">
        <Check size={15} />
        <span>
          {t(
            "wa_hermes_onboarding_bullet_1",
            {},
            "Dedicated container: 2 vCPU and 4 GB RAM"
          )}
        </span>
      </li>
      <li style="display: flex; gap: 8px; align-items: flex-start; margin-bottom: 6px;">
        <Check size={15} />
        <span>
          {t(
            "wa_hermes_onboarding_bullet_2",
            {},
            "Memory and files survive restarts"
          )}
        </span>
      </li>
      <li style="display: flex; gap: 8px; align-items: flex-start; margin-bottom: 6px;">
        <Check size={15} />
        <span>
          {t(
            "wa_hermes_onboarding_bullet_3",
            {},
            "DeepSeek via CornLLM, paid in rubles"
          )}
        </span>
      </li>
    </ul>
    <Button variant="primary" onclick={() => (step = 2)}>
      {t("wa_hermes_onboarding_cta_choose", {}, "Choose a plan")}
      <ChevronRight size={16} />
    </Button>
  </Card>

  {#if step >= 2}
    <Card>
      <h3 style="margin: 0 0 8px; font-size: 16px;">
        {t("wa_hermes_onboarding_plan_title", {}, "Choose a plan")}
      </h3>
      <p style="margin: 0 0 12px; color: var(--muted); font-size: 13px;">
        {t(
          "wa_hermes_onboarding_plan_help",
          {},
          "Both plans include the hosting container. The CornLLM balance powers the agent's replies — once exhausted, the agent stays up but LLM replies pause until you top up."
        )}
      </p>
      <div style="display: grid; gap: 10px;" data-test-id="hosting-plans">
        {#each hostingPlans as plan (plan.key)}
          {@const selected = selectedPlan.key === plan.key}
          <button
            type="button"
            data-test-id={`hosting-plan-${plan.key}`}
            data-selected={selected}
            onclick={() => (selectedPlan = plan)}
            style="
              all: unset;
              cursor: pointer;
              border: 2px solid {selected ? 'var(--accent, #2e7d32)' : 'var(--border, #ddd)'};
              border-radius: 8px;
              padding: 12px;
              background: {selected ? 'var(--surface-accent, #f0f7f0)' : 'transparent'};
              display: block;
              width: 100%;
              text-align: left;
            "
          >
            <div style="display: flex; align-items: center; justify-content: space-between; gap: 8px;">
              <strong>{t(plan.titleKey, {}, plan.titleFallback)}</strong>
              <span style="font-weight: 700;">{plan.priceRub} ₽/мес</span>
            </div>
            <div style="color: var(--muted); font-size: 12px; margin-top: 4px;">
              {t(plan.bulletsKey, {}, plan.bulletsFallback)}
            </div>
            {#if plan.cornllmRubMonthly > 0}
              <div
                style="margin-top: 6px; display: inline-block; padding: 2px 8px; background: var(--surface-accent, #f0f7f0); color: var(--accent, #2e7d32); border-radius: 999px; font-size: 11px;"
              >
                {t(
                  "wa_hermes_onboarding_plan_includes_cornllm",
                  { amount: plan.cornllmRubMonthly },
                  `Includes ${plan.cornllmRubMonthly} ₽/mo CornLLM`
                )}
              </div>
            {/if}
          </button>
        {/each}
      </div>
      <Button
        variant="primary"
        onclick={payWithPlan}
        disabled={methods.length === 0}
        style="margin-top: 12px;"
      >
        {t(
          "wa_hermes_onboarding_cta_pay",
          { plan: t(selectedPlan.titleKey, {}, selectedPlan.titleFallback), price: selectedPlan.priceRub },
          `Pay ${selectedPlan.priceRub} ₽ and launch`
        )}
      </Button>
    </Card>
  {/if}

  {#if step >= 3 || (!hasBotToken && active)}
    <Card>
      <h3 style="margin: 0 0 8px; font-size: 16px;">
        {t("wa_hermes_onboarding_bot_title", {}, "Create your Telegram bot")}
      </h3>
      <ol style="margin: 0 0 12px; padding-left: 18px; font-size: 13px;">
        <li style="margin-bottom: 6px;">
          {t(
            "wa_hermes_onboarding_bot_step_1",
            {},
            "Open @BotFather in Telegram and send /newbot"
          )}
        </li>
        <li style="margin-bottom: 6px;">
          {t(
            "wa_hermes_onboarding_bot_step_2",
            {},
            "Pick a name and @username — BotFather returns a token like 123…:ABC…"
          )}
        </li>
        <li style="margin-bottom: 6px;">
          {t(
            "wa_hermes_onboarding_bot_step_3",
            {},
            "Paste the token below — we attach it to the container and start the agent"
          )}
        </li>
      </ol>
      <div style="display: flex; gap: 6px;">
        <input
          type="text"
          bind:value={botToken}
          placeholder="123456789:ABCdefGHI..."
          style="flex: 1; padding: 8px; border: 1px solid var(--border, #ccc); border-radius: 4px; font-size: 14px;"
        />
        <Button
          variant="primary"
          onclick={saveToken}
          disabled={!botToken.trim() || tokenBusy}
        >
          {tokenBusy
            ? t("wa_hermes_onboarding_saving", {}, "Saving…")
            : t("wa_hermes_onboarding_save", {}, "Save")}
        </Button>
      </div>
      {#if tokenError}
        <p style="margin: 6px 0 0; color: var(--danger); font-size: 12px;">
          {tokenError}
        </p>
      {/if}
      <p style="margin: 6px 0 0; color: var(--muted); font-size: 11px;">
        {t(
          "wa_hermes_onboarding_bot_help",
          {},
          "The token is stored encrypted. We only use it to run your bot."
        )}
      </p>
    </Card>
  {/if}

  {#if tokenOk || (active && tenantStatus && tenantStatus !== "active")}
    <Card>
      <h3 style="margin: 0 0 8px; font-size: 16px;">
        <Server size={15} style="vertical-align: middle; margin-right: 6px;" />
        {t("wa_hermes_onboarding_provisioning_title", {}, "Starting your container…")}
      </h3>
      <p style="margin: 0 0 8px; color: var(--muted); font-size: 13px;">
        {t(
          "wa_hermes_onboarding_provisioning_help",
          {},
          "Creating the CornLLM key, booting the container, and starting Hermes Agent. Usually 20–40 seconds."
        )}
      </p>
      {#if tenantStatus}
        <p style="margin: 0; font-size: 12px;">
          {t("wa_hermes_onboarding_status", {}, "Status:")}
          <code>{tenantStatus}</code>
        </p>
      {/if}
    </Card>
  {/if}

{#if tokenOk && active}
    <Card>
      <h3 style="margin: 0 0 12px; font-size: 16px; color: var(--success, #2e7d32);">
        <Sparkles size={15} style="vertical-align: middle; margin-right: 6px;" />
        {t("wa_hermes_onboarding_done_title", {}, "Done!")}
      </h3>
      <p style="margin: 0 0 12px; color: var(--muted); font-size: 13px;">
        {t(
          "wa_hermes_onboarding_done_help",
          {},
          "Bot is live. Open it in Telegram and say hi — it replies through DeepSeek (CornLLM)."
        )}
      </p>
      {#if subscription?.bot_username}
        <Button
          variant="primary"
          onclick={() => openBotChat(`https://t.me/${subscription?.bot_username}`)}
        >
          {t("wa_open_bot", {}, "Open bot")}
        </Button>
      {/if}
    </Card>
  {/if}
{/if}