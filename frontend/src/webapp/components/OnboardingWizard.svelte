<script lang="ts">
  import { Check, ChevronRight, Copy, Gift, Server, Sparkles, Wallet } from "$components/ui/icons.js";
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
  // ponytail: lifecycle states we already drive via deriveLifecycleView.
  const tenantStatus = $derived(String(subscription?.tenant_status || "").trim() || null);

  let step = $state(1);
  let botToken = $state("");
  let tokenBusy = $state(false);
  let tokenError = $state<string | null>(null);
  let tokenOk = $state(false);
  let tokenCopied = $state(false);

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

  async function copy(text: string) {
    try {
      if (typeof navigator !== "undefined" && navigator.clipboard) {
        await navigator.clipboard.writeText(text);
      }
      tokenCopied = true;
      window.setTimeout(() => (tokenCopied = false), 1500);
    } catch {
      tokenCopied = false;
    }
  }

  function fmtRubles(value: number): string {
    return `${Math.round(value)} ₽`;
  }
</script>

{#if hermesMode && !active}
  <Card class="onboarding-hero">
    <h2 style="margin: 0 0 6px; font-size: 18px;">
      {t("wa_hermes_onboarding_title", {}, "Запустите своего AI-агента в Telegram")}
    </h2>
    <p style="margin: 0 0 12px; color: var(--muted); font-size: 13px;">
      {t(
        "wa_hermes_onboarding_subtitle",
        {},
        "Личный Hermes Agent в Telegram. Работает 24/7 на нашем сервере."
      )}
    </p>
    <ul style="margin: 0 0 14px; padding: 0; list-style: none; font-size: 13px;">
      <li style="display: flex; gap: 8px; align-items: flex-start; margin-bottom: 6px;">
        <Check size={15} />
        <span>
          {t(
            "wa_hermes_onboarding_bullet_1",
            {},
            "Выделенный контейнер: 2 vCPU и 4 GB RAM"
          )}
        </span>
      </li>
      <li style="display: flex; gap: 8px; align-items: flex-start; margin-bottom: 6px;">
        <Check size={15} />
        <span>
          {t(
            "wa_hermes_onboarding_bullet_2",
            {},
            "Память и файлы сохраняются между перезапусками"
          )}
        </span>
      </li>
      <li style="display: flex; gap: 8px; align-items: flex-start; margin-bottom: 6px;">
        <Check size={15} />
        <span>
          {t(
            "wa_hermes_onboarding_bullet_3",
            {},
            "DeepSeek через CornLLM, оплата в рублях"
          )}
        </span>
      </li>
    </ul>
    <Button variant="primary" onclick={() => (step = 2)}>
      {t("wa_hermes_onboarding_cta_choose", {}, "Выбрать тариф")}
      <ChevronRight size={16} />
    </Button>
  </Card>

  {#if step >= 2}
    <Card>
      <h3 style="margin: 0 0 8px; font-size: 16px;">
        {t("wa_hermes_onboarding_plan_title", {}, "Выберите тариф")}
      </h3>
      <p style="margin: 0 0 12px; color: var(--muted); font-size: 13px;">
        {t(
          "wa_hermes_onboarding_plan_help",
          {},
          "Тариф включает хостинг контейнера. Баланс CornLLM расходуется на ответы модели — после исчерпания агент продолжит работать, но ответы LLM остановятся до пополнения."
        )}
      </p>
      <div style="display: grid; gap: 10px;">
        <div
          class="tariff-card"
          style="border: 1px solid var(--border, #ddd); border-radius: 8px; padding: 12px;"
        >
          <strong>{t("wa_hermes_tariff_basic", {}, "Базовый")}</strong>
          <div style="color: var(--muted); font-size: 12px;">
            300 ₽/мес · 2 vCPU · 4 GB RAM · без включённого баланса CornLLM
          </div>
        </div>
        <div
          class="tariff-card"
          style="border: 1px solid var(--border, #ddd); border-radius: 8px; padding: 12px;"
        >
          <strong>{t("wa_hermes_tariff_plus", {}, "Плюс")}</strong>
          <div style="color: var(--muted); font-size: 12px;">
            500 ₽/мес · 2 vCPU · 4 GB RAM · 300 ₽ баланса CornLLM включено
          </div>
        </div>
      </div>
      <Button
        variant="primary"
        onclick={() => openPaymentModal()}
        disabled={methods.length === 0}
        style="margin-top: 12px;"
      >
        <Wallet size={15} />
        {t("wa_hermes_onboarding_cta_pay", {}, "Оплатить и запустить")}
      </Button>
    </Card>
  {/if}

  {#if step >= 3 || (!hasBotToken && active)}
    <Card>
      <h3 style="margin: 0 0 8px; font-size: 16px;">
        {t("wa_hermes_onboarding_bot_title", {}, "Создайте своего Telegram-бота")}
      </h3>
      <ol style="margin: 0 0 12px; padding-left: 18px; font-size: 13px;">
        <li style="margin-bottom: 6px;">
          {t(
            "wa_hermes_onboarding_bot_step_1",
            {},
            "Откройте @BotFather в Telegram и отправьте /newbot"
          )}
        </li>
        <li style="margin-bottom: 6px;">
          {t(
            "wa_hermes_onboarding_bot_step_2",
            {},
            "Задайте имя и @username бота — BotFather вернёт токен вида 123…:ABC…"
          )}
        </li>
        <li style="margin-bottom: 6px;">
          {t(
            "wa_hermes_onboarding_bot_step_3",
            {},
            "Вставьте токен ниже — мы привяжем его к контейнеру и запустим агента"
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
          {tokenBusy ? "..." : t("wa_hermes_onboarding_save", {}, "Сохранить")}
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
          "Токен хранится зашифрованным. Мы используем его только для запуска вашего бота."
        )}
      </p>
    </Card>
  {/if}

  {#if tokenOk || (active && tenantStatus && tenantStatus !== "active")}
    <Card>
      <h3 style="margin: 0 0 8px; font-size: 16px;">
        <Server size={15} style="vertical-align: middle; margin-right: 6px;" />
        {t("wa_hermes_onboarding_provisioning_title", {}, "Запускаем контейнер…")}
      </h3>
      <p style="margin: 0 0 8px; color: var(--muted); font-size: 13px;">
        {t(
          "wa_hermes_onboarding_provisioning_help",
          {},
          "Создаём ключ CornLLM, поднимаем контейнер и запускаем Hermes Agent. Обычно занимает 20–40 секунд."
        )}
      </p>
      {#if tenantStatus}
        <p style="margin: 0; font-size: 12px;">
          {t("wa_hermes_onboarding_status", {}, "Статус:")}
          <code>{tenantStatus}</code>
        </p>
      {/if}
    </Card>
  {/if}

  {#if tokenOk && active}
    <Card>
      <h3 style="margin: 0 0 8px; font-size: 16px; color: var(--success, #2e7d32);">
        <Sparkles size={15} style="vertical-align: middle; margin-right: 6px;" />
        {t("wa_hermes_onboarding_done_title", {}, "Готово!")}
      </h3>
      <p style="margin: 0 0 12px; color: var(--muted); font-size: 13px;">
        {t(
          "wa_hermes_onboarding_done_help",
          {},
          "Бот запущен. Откройте его в Telegram и напишите — он ответит через DeepSeek (CornLLM)."
        )}
      </p>
      {#if appSettings?.bot_username}
        <Button
          variant="primary"
          onclick={() => {
            if (typeof window !== "undefined") {
              window.open(`https://t.me/${appSettings.bot_username}`, "_blank");
            }
          }}
        >
          {t("wa_open_bot", {}, "Открыть бота")}
        </Button>
      {/if}
    </Card>
  {/if}
{/if}