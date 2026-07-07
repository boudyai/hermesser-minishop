<script lang="ts">
  import Button from "$components/ui/button.svelte";
  import Card from "$components/ui/card.svelte";
  import { Copy, Eye, EyeOff, Key } from "$components/ui/icons.js";

  type UnknownRecord = Record<string, unknown>;
  type ApiUnchecked = (
    path: string,
    options?: Parameters<typeof fetch>[1]
  ) => Promise<Record<string, unknown>>;

  let {
    subscription = {},
    appSettings = {},
    apiUnchecked,
    t = (key: string, _params?: UnknownRecord, fallback?: string) => fallback || key,
  }: {
    subscription?: UnknownRecord;
    appSettings?: UnknownRecord;
    apiUnchecked?: ApiUnchecked;
    t?: (key: string, params?: UnknownRecord, fallback?: string) => string;
  } = $props();

  const hermesMode = $derived(String(appSettings?.panel_write_mode || "") === "hermes");
  const active = $derived(Boolean(subscription?.active));

  let revealed = $state(false);
  let apiKey = $state<string | null>(null);
  let keyId = $state<string | null>(null);
  let busy = $state(false);
  let error = $state<string | null>(null);
  let copied = $state(false);

  async function load() {
    if (!apiUnchecked) return;
    busy = true;
    error = null;
    try {
      const data = (await apiUnchecked("/tenant/cornllm-key")) as {
        api_key?: string;
        key_id?: string;
      };
      apiKey = data?.api_key ?? null;
      keyId = data?.key_id ?? null;
    } catch (e) {
      error = e instanceof Error ? e.message : "fetch_failed";
      apiKey = null;
    } finally {
      busy = false;
    }
  }

  function maskKey(key: string): string {
    if (key.length <= 8) return "••••";
    return `${key.slice(0, 7)}••••${key.slice(-4)}`;
  }

  async function copyKey() {
    if (!apiKey) return;
    try {
      if (typeof navigator !== "undefined" && navigator.clipboard) {
        await navigator.clipboard.writeText(apiKey);
      } else if (typeof document !== "undefined") {
        const ta = document.createElement("textarea");
        ta.value = apiKey;
        document.body.appendChild(ta);
        ta.select();
        document.execCommand("copy");
        document.body.removeChild(ta);
      }
      copied = true;
      window.setTimeout(() => (copied = false), 2000);
    } catch {
      error = "copy_failed";
    }
  }

  $effect(() => {
    if (hermesMode && active && apiKey === null && !busy) {
      load();
    }
  });
</script>

{#if hermesMode && active}
  <Card compact>
    <div
      style="display: flex; gap: 8px; align-items: center; justify-content: space-between; flex-wrap: wrap;"
    >
      <div
        style="display: flex; gap: 6px; align-items: center; color: var(--muted); font-size: 13px;"
      >
        <Key size={15} />
        <span>{t("wa_settings_cornllm_key_label", {}, "CornLLM API key")}</span>
      </div>
      <div style="display: flex; gap: 6px; align-items: center;">
        <Button variant="secondary" onclick={load} disabled={busy}>
          {busy
            ? t("wa_settings_cornllm_key_loading", {}, "Loading…")
            : t("wa_settings_cornllm_key_refresh", {}, "Refresh")}
        </Button>
      </div>
    </div>
    {#if error}
      <p style="margin: 8px 0 0; color: var(--danger); font-size: 12px;">
        {t("wa_settings_cornllm_key_fetch_failed", { error }, `Could not load key: ${error}`)}
      </p>
    {:else if apiKey}
      <div
        style="margin-top: 8px; padding: 8px; background: var(--surface-subtle); border: 1px solid var(--surface-subtle-border); border-radius: 6px; font-family: ui-monospace, monospace; font-size: 12px; word-break: break-all;"
      >
        {revealed ? apiKey : maskKey(apiKey)}
      </div>
      <p style="margin: 4px 0 0; color: var(--muted); font-size: 11px;">
        {t(
          "wa_settings_cornllm_key_warning",
          {},
          "This key charges your CornLLM balance. Don't publish it."
        )}
      </p>
      <div style="display: flex; gap: 6px; margin-top: 8px;">
        <Button variant="secondary" onclick={() => (revealed = !revealed)}>
          {#if revealed}
            <EyeOff size={14} />
            {t("wa_settings_cornllm_key_hide", {}, "Hide")}
          {:else}
            <Eye size={14} />
            {t("wa_settings_cornllm_key_show", {}, "Show")}
          {/if}
        </Button>
        <Button variant="secondary" onclick={copyKey}>
          <Copy size={14} />
          {copied
            ? t("wa_settings_cornllm_key_copied", {}, "Copied")
            : t("wa_settings_cornllm_key_copy", {}, "Copy")}
        </Button>
      </div>
    {/if}
  </Card>
{/if}
