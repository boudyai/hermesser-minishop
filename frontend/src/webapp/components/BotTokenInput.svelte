<script lang="ts">
  import Button from "$components/ui/button.svelte";
  import Card from "$components/ui/card.svelte";

  type ApiUnchecked = (
    path: string,
    options?: Parameters<typeof fetch>[1]
  ) => Promise<Record<string, unknown>>;
  const missingApi: ApiUnchecked = async () => ({ ok: false, error: "api_unavailable" });

  let tokenDraft = $state("");
  let busy = $state(false);
  let error = $state<string | null>(null);

  async function submitToken() {
    const token = tokenDraft.trim();
    if (!token || !token.includes(":") || !token.split(":", 1)[0].match(/^\d+$/)) {
      error = "Token must look like 123456789:ABCdef...";
      return;
    }
    busy = true;
    error = null;
    try {
      const data = await apiUnchecked("/account/bot_token", {
        method: "PUT",
        body: JSON.stringify({ bot_token: token }),
      });
      if (data.ok === false) {
        const code = String(data.error || "update_failed");
        const messages: Record<string, string> = {
          invalid_bot_token: "Telegram rejected this token. Check @BotFather.",
          telegram_check_failed: "Could not reach Telegram. Try again.",
          api_unavailable: "API client is not ready. Reload the app.",
          access_denied: "Session expired. Reload the app.",
          unauthorized: "Session expired. Reload the app.",
        };
        error = messages[code] || `Failed: ${code}`;
        return;
      }
      tokenDraft = "";
      // Reload to pick up the updated /api/me (has_bot_token=true)
      window.location.reload();
    } catch (e) {
      error = e instanceof Error ? e.message : "Network error";
    } finally {
      busy = false;
    }
  }

  type AnyRecord = Record<string, any>;
  let {
    appSettings = {},
    apiUnchecked = missingApi,
  }: { appSettings?: AnyRecord; apiUnchecked?: ApiUnchecked } = $props();
  const hermesMode = $derived(String(appSettings?.panel_write_mode || "") === "hermes");
</script>

{#if hermesMode}
  <Card>
    <h3 style="margin: 0 0 8px; font-size: 15px;">🤖 Bot token</h3>
    <p style="margin: 0 0 10px; color: var(--muted); font-size: 12px;">
      Создайте бота через <a href="https://t.me/BotFather" target="_blank" rel="noopener"
        >@BotFather</a
      > и вставьте токен сюда. Бот будет принимать сообщения от ваших клиентов.
    </p>
    <details style="margin-bottom: 10px;">
      <summary style="cursor: pointer; color: var(--muted); font-size: 12px;"
        >Как получить токен?</summary
      >
      <ol style="font-size: 12px; color: var(--muted); padding-left: 20px; margin: 8px 0 0;">
        <li>Откройте <a href="https://t.me/BotFather" target="_blank">@BotFather</a> в Telegram</li>
        <li>Отправьте <code>/newbot</code> и следуйте инструкциям</li>
        <li>Скопируйте токен вида <code>123456789:ABCdef...</code></li>
        <li>Вставьте его в поле ниже</li>
      </ol>
    </details>
    <div style="display: flex; gap: 8px; align-items: center;">
      <input
        type="text"
        placeholder="123456789:ABCdef..."
        bind:value={tokenDraft}
        autocomplete="off"
        spellcheck="false"
        style="flex: 1; padding: 8px 10px; border: 1px solid var(--surface-subtle-border); border-radius: 8px; background: var(--surface-subtle); color: var(--text); font-family: ui-monospace, monospace; font-size: 12px;"
      />
      <Button onclick={submitToken} disabled={busy}>
        {busy ? "Сохранение..." : "Сохранить"}
      </Button>
    </div>
    {#if error}
      <p style="margin: 8px 0 0; color: var(--danger); font-size: 12px;">{error}</p>
    {/if}
  </Card>
{/if}
