<script lang="ts">
  import Button from "$components/ui/button.svelte";
  import Card from "$components/ui/card.svelte";
  import { RefreshCw, Activity, FileText, ExternalLink } from "$components/ui/icons.js";

  type AnyRecord = Record<string, any>;
  let {
    subscription = {},
    appSettings = {},
  }: { subscription?: AnyRecord; appSettings?: AnyRecord } = $props();

  const hermesMode = $derived(String(appSettings?.panel_write_mode || "") === "hermes");
  const active = $derived(Boolean(subscription?.active));
  const botUsername = $derived(
    String(subscription?.bot_username || appSettings?.bot_username || "").trim()
  );
  const tMeUrl = $derived(botUsername ? `https://t.me/${botUsername}` : "");

  let busy = $state(false);
  let busyAction = $state<"restart" | "logs-refresh" | "">("");
  let error = $state<string | null>(null);
  let info = $state<string | null>(null);

  let quotaMax = $state<number | null>(null);
  let quotaSpent = $state<number | null>(null);
  let quotaRemaining = $state<number | null>(null);
  let logs = $state("");
  let logsOpen = $state(false);

  async function callApi(path: string, method: "GET" | "POST" = "GET"): Promise<unknown> {
    const resp = await fetch(path, {
      method,
      headers: { "Content-Type": "application/json" },
      credentials: "include",
    });
    const data = await resp.json().catch(() => ({}));
    if (!resp.ok) {
      const code = (data as { error?: string })?.error || `http_${resp.status}`;
      throw new Error(code);
    }
    return data;
  }

  async function refreshStatus() {
    busy = true;
    busyAction = "restart";
    error = null;
    try {
      await callApi("/api/tenant/restart", "POST");
      info = "Restart queued — bot will be back in ~30s.";
    } catch (e) {
      error = e instanceof Error ? e.message : "Restart failed";
    } finally {
      busy = false;
      busyAction = "";
    }
  }

  async function refreshQuota() {
    try {
      const data = (await callApi("/api/tenant/quota")) as {
        max_budget?: number;
        spent?: number;
        remaining?: number;
      };
      quotaMax = data.max_budget ?? null;
      quotaSpent = data.spent ?? null;
      quotaRemaining = data.remaining ?? null;
    } catch {
      // Quota not available — non-fatal, just hide the card.
    }
  }

  async function loadLogs() {
    busy = true;
    busyAction = "logs-refresh";
    error = null;
    try {
      const data = (await callApi("/api/tenant/logs")) as { logs?: string };
      logs = data.logs || "";
      logsOpen = true;
    } catch (e) {
      error = e instanceof Error ? e.message : "Logs failed";
    } finally {
      busy = false;
      busyAction = "";
    }
  }

  $effect(() => {
    if (hermesMode && active) {
      refreshQuota();
    }
  });

  function fmtUsd(v: number | null): string {
    if (v === null) return "—";
    if (v >= 1) return `$${v.toFixed(2)}`;
    return `$${v.toFixed(3)}`;
  }
</script>

{#if hermesMode && active}
  <Card compact>
    <div
      style="display: flex; gap: 8px; align-items: center; justify-content: space-between; flex-wrap: wrap;"
    >
      <div
        style="display: flex; gap: 6px; align-items: center; color: var(--muted); font-size: 13px;"
      >
        <Activity size={15} />
        <span>Статус бота</span>
      </div>
      <div style="display: flex; gap: 6px; align-items: center;">
        {#if tMeUrl}
          <a href={tMeUrl} target="_blank" rel="noopener">
            <Button variant="secondary">
              <ExternalLink size={14} />
              @{tMeUrl.split("/").pop() || botUsername}
            </Button>
          </a>
        {/if}
        <Button variant="secondary" onclick={loadLogs} disabled={busy}>
          <FileText size={14} />
          Логи
        </Button>
        <Button variant="secondary" onclick={refreshStatus} disabled={busy}>
          <RefreshCw size={14} class={busyAction === "restart" ? "spinning" : ""} />
          Перезагрузить
        </Button>
      </div>
    </div>
    {#if quotaMax !== null}
      <div
        style="margin-top: 8px; display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; font-size: 12px;"
      >
        <div>
          <small style="color: var(--muted);">Бюджет</small>
          <div><strong>{fmtUsd(quotaMax)}</strong></div>
        </div>
        <div>
          <small style="color: var(--muted);">Потрачено</small>
          <div><strong>{fmtUsd(quotaSpent)}</strong></div>
        </div>
        <div>
          <small style="color: var(--muted);">Осталось</small>
          <div>
            <strong
              style={quotaRemaining !== null && quotaRemaining < 1 ? "color: var(--danger)" : ""}
            >
              {fmtUsd(quotaRemaining)}
            </strong>
          </div>
        </div>
      </div>
    {/if}
    {#if logsOpen}
      <div style="margin-top: 10px;">
        <Button variant="secondary" onclick={loadLogs} disabled={busy}>
          <RefreshCw size={12} class={busyAction === "logs-refresh" ? "spinning" : ""} />
          Обновить логи
        </Button>
        <pre
          style="margin-top: 8px; padding: 8px; background: var(--surface-subtle); border: 1px solid var(--surface-subtle-border); border-radius: 8px; font-family: ui-monospace, monospace; font-size: 11px; max-height: 240px; overflow: auto; white-space: pre-wrap; word-break: break-all;">{logs ||
            "(empty)"}</pre>
      </div>
    {/if}
    {#if error}
      <p style="margin: 6px 0 0; color: var(--danger); font-size: 12px;">{error}</p>
    {/if}
    {#if info}
      <p style="margin: 6px 0 0; color: var(--muted); font-size: 12px;">{info}</p>
    {/if}
  </Card>
{/if}
