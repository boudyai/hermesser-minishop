<script lang="ts">
  import Button from "$components/ui/button.svelte";
  import Card from "$components/ui/card.svelte";

  type AnyRecord = Record<string, any>;
  let {
    appSettings = {},
    subscription = {},
  }: { appSettings?: AnyRecord; subscription?: AnyRecord } = $props();

  const hermesMode = $derived(String(appSettings?.panel_write_mode || "") === "hermes");
  const hasBotToken = $derived(Boolean(appSettings?.has_bot_token));
  const active = $derived(Boolean(subscription?.active));

  // Ponytail: the four tenant_* fields are emitted by the webapp serializer
  // (``_serialize_subscription`` in hermes mode) and reflect provisioning-core
  // state. They stay null in non-hermes mode or when the core is unreachable.
  const tenantStatus = $derived(String(subscription?.tenant_status || "").trim() || null);
  const tenantActualState = $derived(
    String(subscription?.tenant_actual_state || "").trim() || null
  );
  const tenantLastChange = $derived(
    String(subscription?.tenant_last_state_change || "").trim() || null
  );

  // States where the tenant is still being built — show a "setting up" card.
  const isProvisioning = $derived(
    Boolean(
      hermesMode &&
      !active &&
      hasBotToken &&
      tenantStatus &&
      [
        "created",
        "awaiting_payment",
        "paid",
        "provisioning_litellm_key",
        "provisioning_vm",
      ].includes(tenantStatus)
    )
  );

  // Hard error from provisioning — user can't proceed without help.
  const isError = $derived(
    Boolean(hermesMode && !active && hasBotToken && tenantStatus === "error")
  );

  // Grace period: tenant still running, but payment is lapsing.
  const isGracePeriod = $derived(
    Boolean(hermesMode && !active && hasBotToken && tenantStatus === "payment_expiring")
  );

  // Suspended: container is stopped, user needs to renew to bring it back.
  const isSuspended = $derived(
    Boolean(hermesMode && !active && hasBotToken && tenantStatus === "suspended")
  );

  // Deleting: tenant is being torn down. Nothing for the user to do.
  const isDeleting = $derived(
    Boolean(hermesMode && !active && hasBotToken && tenantStatus === "deleting")
  );

  let step = $state(1);
  let expanded = $state(false);
  let refreshing = $state(false);

  function reload() {
    refreshing = true;
    // The home payload is server-rendered per page load; the simplest way to
    // pull fresh tenant state is a hard reload (the 5s server-side cache
    // means a quick F5 is enough to converge on the latest core state).
    if (typeof window !== "undefined") {
      window.location.reload();
    }
  }

  const stepStyle =
    "display: inline-flex; align-items: center; justify-content: center; width: 28px; height: 28px; border-radius: 50%; background: var(--accent); color: white; font-size: 13px; font-weight: 700; margin-right: 8px;";

  function fmtElapsed(iso: string): string {
    const t = Date.parse(iso);
    if (!Number.isFinite(t)) return "";
    const seconds = Math.max(0, Math.floor((Date.now() - t) / 1000));
    if (seconds < 60) return `${seconds} сек назад`;
    const minutes = Math.floor(seconds / 60);
    if (minutes < 60) return `${minutes} мин назад`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours} ч назад`;
    const days = Math.floor(hours / 24);
    return `${days} дн назад`;
  }
</script>

{#if hermesMode && !active}
  {#if !hasBotToken}
    <Card>
      <h3 style="margin: 0 0 12px; font-size: 16px;">🚀 Запустите своего AI-агента</h3>
      <p style="margin: 0 0 14px; color: var(--muted); font-size: 13px;">
        Создайте бота в Telegram, вставьте токен, и мы развернём его в нашем защищённом контейнере.
      </p>

      <ol style="margin: 0 0 14px; padding: 0; list-style: none;">
        <li
          style="display: flex; align-items: flex-start; margin-bottom: 10px; opacity: {step >= 1
            ? 1
            : 0.5};"
        >
          <span style={stepStyle}>1</span>
          <div>
            <strong>Создайте бота</strong>
            <div style="color: var(--muted); font-size: 12px; margin-top: 2px;">
              Откройте <a href="https://t.me/BotFather" target="_blank" rel="noopener">@BotFather</a
              >
              в Telegram, отправьте <code>/newbot</code>, задайте имя и @username
            </div>
          </div>
        </li>
        <li
          style="display: flex; align-items: flex-start; margin-bottom: 10px; opacity: {step >= 2
            ? 1
            : 0.5};"
        >
          <span style={stepStyle}>2</span>
          <div>
            <strong>Скопируйте токен</strong>
            <div style="color: var(--muted); font-size: 12px; margin-top: 2px;">
              BotFather отправит токен вида <code>123456789:ABCdef...</code>
            </div>
          </div>
        </li>
        <li
          style="display: flex; align-items: flex-start; margin-bottom: 10px; opacity: {step >= 3
            ? 1
            : 0.5};"
        >
          <span style={stepStyle}>3</span>
          <div>
            <strong>Вставьте токен в Настройках</strong>
            <div style="color: var(--muted); font-size: 12px; margin-top: 2px;">
              Перейдите во вкладку "Настройки" ниже и вставьте токен
            </div>
          </div>
        </li>
      </ol>

      <Button onclick={() => (expanded = !expanded)}>
        {expanded ? "Скрыть детали" : "Что умеет мой бот?"}
      </Button>
      {#if expanded}
        <div
          style="margin-top: 12px; padding: 12px; background: var(--surface-subtle); border-radius: 8px; font-size: 12px; color: var(--muted);"
        >
          <p style="margin: 0 0 8px;">
            <strong style="color: var(--text);">Hermes Agent</strong> — AI-агент, который отвечает вашим
            клиентам в Telegram.
          </p>
          <p style="margin: 0 0 8px;">• Понимает текст, голосовые сообщения, картинки</p>
          <p style="margin: 0 0 8px;">• Использует инструменты (веб-поиск, браузер)</p>
          <p style="margin: 0;">• Работает 24/7 в защищённом контейнере</p>
        </div>
      {/if}
    </Card>
  {:else if isProvisioning}
    <Card>
      <h3 style="margin: 0 0 8px; font-size: 16px;">⚙️ Разворачиваем вашего бота…</h3>
      <p style="margin: 0 0 6px; color: var(--muted); font-size: 13px;">
        Обычно занимает 20–40 секунд. Создаём контейнер, ключ LLM и запускаем Hermes Agent.
      </p>
      <p style="margin: 0 0 12px; color: var(--muted); font-size: 12px;">
        Статус: <code>{tenantStatus}</code>
        {#if tenantActualState}
          · фактически: <code>{tenantActualState}</code>
        {/if}
        {#if tenantLastChange}
          · обновлено {fmtElapsed(tenantLastChange)}
        {/if}
      </p>
      <Button variant="secondary" onclick={reload} disabled={refreshing}>
        {refreshing ? "Обновляем…" : "Обновить статус"}
      </Button>
    </Card>
  {:else if isError}
    <Card>
      <h3 style="margin: 0 0 8px; font-size: 16px; color: var(--danger);">
        ❌ Не удалось развернуть бот
      </h3>
      <p style="margin: 0 0 12px; color: var(--muted); font-size: 13px;">
        Развёртывание завершилось с ошибкой. Попробуйте обновить статус — обычно проблема решается
        автоматически после ретрая.
      </p>
      <div style="display: flex; gap: 8px; flex-wrap: wrap;">
        <Button onclick={reload} disabled={refreshing}>
          {refreshing ? "Обновляем…" : "Повторить"}
        </Button>
        <Button variant="secondary" onclick={() => (window.location.href = "/settings")}>
          Открыть настройки
        </Button>
      </div>
    </Card>
  {:else if isGracePeriod}
    <Card>
      <h3 style="margin: 0 0 8px; font-size: 16px;">⏳ Льготный период</h3>
      <p style="margin: 0 0 8px; color: var(--muted); font-size: 13px;">
        Бот ещё работает, но оплата не продлена. Продлите подписку, чтобы не потерять данные.
      </p>
      {#if subscription?.end_date_text}
        <p style="margin: 0 0 12px; font-size: 12px;">
          Активен до: <strong>{subscription.end_date_text}</strong>
        </p>
      {/if}
      <Button onclick={() => (window.location.href = "/payment")}>Продлить подписку</Button>
    </Card>
  {:else if isSuspended}
    <Card>
      <h3 style="margin: 0 0 8px; font-size: 16px;">💤 Бот приостановлен</h3>
      <p style="margin: 0 0 12px; color: var(--muted); font-size: 13px;">
        Контейнер остановлен. Чтобы бот снова заработал, продлите подписку или активируйте пробный
        период заново.
      </p>
      <Button onclick={() => (window.location.href = "/payment")}>Продлить</Button>
    </Card>
  {:else if isDeleting}
    <Card>
      <h3 style="margin: 0 0 8px; font-size: 16px; color: var(--muted);">🗑 Бот удаляется…</h3>
      <p style="margin: 0 0 12px; color: var(--muted); font-size: 13px;">
        Контейнер и связанные данные в процессе удаления. Это займёт несколько минут.
      </p>
    </Card>
  {/if}
{/if}
