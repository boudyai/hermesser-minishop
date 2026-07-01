<script lang="ts">
  import Button from "$components/ui/button.svelte";
  import Card from "$components/ui/card.svelte";

  type AnyRecord = Record<string, any>;
  let { appSettings = {} }: { appSettings?: AnyRecord } = $props();

  const hermesMode = $derived(String(appSettings?.panel_write_mode || "") === "hermes");
  const hasBotToken = $derived(Boolean(appSettings?.has_bot_token));
  const active = $derived((appSettings?.subscription_active as boolean | undefined) ?? false);

  let step = $state(1);
  let expanded = $state(false);

  // ponytail: inline mini-CSS keeps the wizard self-contained; no
  // design-token churn.
  const stepStyle =
    "display: inline-flex; align-items: center; justify-content: center; width: 28px; height: 28px; border-radius: 50%; background: var(--accent); color: white; font-size: 13px; font-weight: 700; margin-right: 8px;";
</script>

{#if hermesMode && !active && !hasBotToken}
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
            Откройте <a href="https://t.me/BotFather" target="_blank" rel="noopener">@BotFather</a>
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
{/if}
