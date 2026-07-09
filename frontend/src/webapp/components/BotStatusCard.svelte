<script lang="ts">
  import Button from "$components/ui/button.svelte";
  import Card from "$components/ui/card.svelte";
  import { RefreshCw, Activity, FileText, Pause, Play } from "$components/ui/icons.js";

  type AnyRecord = Record<string, any>;
  type ApiUnchecked = (
    path: string,
    options?: Parameters<typeof fetch>[1]
  ) => Promise<Record<string, unknown>>;
  const missingApi: ApiUnchecked = async () => ({ ok: false, error: "api_unavailable" });
  let {
    subscription = {},
    appSettings = {},
    apiUnchecked = missingApi,
    t = (key: string, _params?: AnyRecord, fallback?: string) => fallback || key,
  }: {
    subscription?: AnyRecord;
    appSettings?: AnyRecord;
    apiUnchecked?: ApiUnchecked;
    t?: (
      key: string,
      params?: AnyRecord,
      fallback?: string
    ) => string;
  } = $props();

  const hermesMode = $derived(String(appSettings?.panel_write_mode || "") === "hermes");
  const active = $derived(Boolean(subscription?.active));
  // ponytail: the core rejects restart/logs actions on tenants in
  // non-actionable states (deleting, deleted, archived) with a 409.
  // Disable the buttons here so the user doesn't keep seeing failures
  // while the tenant is being torn down.
  const tenantStatus = $derived(
    String(subscription?.tenant_status || subscription?.status || "").toLowerCase()
  );
  const actionsEnabled = $derived(
    active && !["deleting", "deleted", "archived", "suspended"].includes(tenantStatus)
  );

  let busy = $state(false);
  let busyAction = $state<"restart" | "logs-refresh" | "">("");
  let confirmRestart = $state(false);
  let error = $state<string | null>(null);
  let info = $state<string | null>(null);

  let quotaMax = $state<number | null>(null);
  let quotaSpent = $state<number | null>(null);
  let quotaRemaining = $state<number | null>(null);
  let logs = $state("");
  let logsOpen = $state(false);

  async function callApi(path: string, method: "GET" | "POST" = "GET"): Promise<unknown> {
    const data = await apiUnchecked(path, {
      method,
    });
    if (data.ok === false) {
      const code = String(data.error || "api_failed");
      throw new Error(code);
    }
    return data;
  }

  function deriveRemaining(
    max: number | null,
    spent: number | null,
    cached: number | null
  ): number | null {
    // ponytail: trust max_budget - spent over the cached remaining
    // column. The cached remaining lags topups because the server
    // updates max_budget synchronously but only refreshes spent via
    // the worker's fetch_quota cycle. After a +5 USD topup on a
    // +10 USD budget the user used to see "remaining=10" instead
    // of "remaining=15" until the next refresh.
    if (max !== null && spent !== null) {
      return Math.max(0, max - spent);
    }
    return cached;
  }

  function askRestart() {
    confirmRestart = true;
  }

  function cancelRestart() {
    confirmRestart = false;
  }

  async function confirmRestartAction() {
    busy = true;
    busyAction = "restart";
    error = null;
    confirmRestart = false;
    try {
      await callApi("/tenant/restart", "POST");
      info = t(
        "wa_hermes_restart_queued",
        {},
        "Restart queued. Bot returns in ~30 seconds."
      );
    } catch (e) {
      error = e instanceof Error ? e.message : "Restart failed";
    } finally {
      busy = false;
      busyAction = "";
    }
  }

  // ponytail: pause = vacation mode (no countdown, resumable). Start =
  // resume from paused (reuses /activate). Distinct from Suspend (destructive
  // 7-day auto-delete) — Suspend lives in TenantDangerZone, not here.
  async function doPause() {
    busy = true;
    busyAction = "restart";
    error = null;
    try {
      const data = (await callApi("/tenant/pause", "POST")) as {
        ok?: boolean;
        status?: string;
      };
      if (data.status === "paused") {
        info = t("wa_hermes_pause_success", {}, "Container paused. Click Start to resume.");
      }
      setTimeout(() => window.location.reload(), 1000);
    } catch (e) {
      error = e instanceof Error ? e.message : "Pause failed";
    } finally {
      busy = false;
      busyAction = "";
    }
  }

  async function doStart() {
    busy = true;
    busyAction = "restart";
    error = null;
    try {
      const data = (await callApi("/tenant/start", "POST")) as {
        ok?: boolean;
        status?: string;
      };
      if (data.status === "active") {
        info = t("wa_hermes_start_success", {}, "Container is starting. Allow ~30 seconds.");
      }
      setTimeout(() => window.location.reload(), 1000);
    } catch (e) {
      error = e instanceof Error ? e.message : "Start failed";
    } finally {
      busy = false;
      busyAction = "";
    }
  }

  async function refreshQuota() {
    try {
      const data = (await callApi("/tenant/quota")) as {
        max_budget?: number;
        spent?: number;
        remaining?: number;
      };
      quotaMax = data.max_budget ?? null;
      quotaSpent = data.spent ?? null;
      quotaRemaining = deriveRemaining(
        data.max_budget ?? null,
        data.spent ?? null,
        data.remaining ?? null
      );
    } catch {
      // Quota not available — non-fatal, just hide the card.
    }
  }

  async function loadLogs() {
    busy = true;
    busyAction = "logs-refresh";
    error = null;
    try {
      // ponytail: GET /tenant/logs returns the cached `last_logs`
      // row from the core, which is only refreshed after a
      // fetch_logs job runs. POST /tenant/logs/refresh enqueues
      // that job; the cached value updates on success. The
      // executor drains in <1s on the worker, but a race between
      // the immediate follow-up GET and the worker write used to
      // show the previous fetch. Poll a couple of times before
      // giving up so we usually pick up the freshest tail.
      await callApi("/tenant/logs/refresh", "POST");
      let latest = "";
      for (let attempt = 0; attempt < 4; attempt++) {
        if (attempt > 0) {
          await new Promise((resolve) => window.setTimeout(resolve, 600));
        }
        const data = (await callApi("/tenant/logs")) as { logs?: string };
        if (data.logs && data.logs.length > 0) {
          latest = data.logs;
          // First non-empty tail — keep polling once more so a
          // slightly-newer write beats us, but stop if we already
          // have a stable read.
          if (attempt >= 1) break;
        } else {
          latest = "";
        }
      }
      logs = latest;
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
      // ponytail: the server's quota GET now commits and enqueues a
      // fetch_quota job, but the worker still needs ~5-10s to drain
      // it. Refresh the card once after a short delay so a stale
      // "remaining=10" after a recent topup gets corrected without
      // the user having to navigate away and back.
      refreshQuota();
      const timer = window.setTimeout(refreshQuota, 7_000);
      return () => window.clearTimeout(timer);
    }
  });

  // ponytail: tell the user why the action buttons are disabled
  // instead of letting them click and see 409 errors.
  const stateNotice = $derived.by(() => {
    if (tenantStatus === "deleting")
      return t(
        "wa_hermes_status_card_deleting",
        {},
        "Deleting… actions unavailable"
      );
    if (tenantStatus === "suspended")
      return t(
        "wa_hermes_status_card_suspended",
        {},
        "Suspended. Resume via your subscription."
      );
    if (tenantStatus === "deleted" || tenantStatus === "archived")
      return t("wa_hermes_status_card_deleted", {}, "Deleted. Create a new bot.");
    return null;
  });

  function fmtUsd(v: number | null): string {
    if (v === null) return "—";
    // ponytail: v is already fractional USD from LiteLLM. Drop cents
    // for whole-dollar amounts, keep them when fractional.
    if (Math.abs(v - Math.round(v)) < 1e-6) {
      return `$${Math.round(v)}`;
    }
    return `$${v.toFixed(2)}`;
  }
</script>

{#if hermesMode && active}
  <Card compact>
    {#if stateNotice}
      <p style="margin: 0 0 8px; color: var(--muted); font-size: 12px;">{stateNotice}</p>
    {/if}
    <div
      style="display: flex; gap: 8px; align-items: center; justify-content: space-between; flex-wrap: wrap;"
    >
      <div
        style="display: flex; gap: 6px; align-items: center; color: var(--muted); font-size: 13px;"
      >
        <Activity size={15} />
        <span>{t("wa_hermes_status_card_label", {}, "Bot status")}</span>
      </div>
      <div style="display: flex; gap: 6px; align-items: center;">
        <Button variant="secondary" onclick={loadLogs} disabled={busy || !actionsEnabled}>
          <FileText size={14} />
          {t("logs", {}, "Logs")}
        </Button>
        {#if tenantStatus === "active"}
          <Button variant="secondary" onclick={doPause} disabled={busy}>
            <Pause size={14} />
            {t("tenant.action.pause", {}, "Pause")}
          </Button>
        {/if}
        {#if tenantStatus === "paused"}
          <Button variant="secondary" onclick={doStart} disabled={busy}>
            <Play size={14} />
            {t("tenant.action.start", {}, "Start")}
          </Button>
        {/if}
        <Button variant="secondary" onclick={askRestart} disabled={busy || !actionsEnabled}>
          <RefreshCw size={14} class={busyAction === "restart" ? "spinning" : ""} />
          {t("restart", {}, "Restart")}
        </Button>
      </div>
    </div>
    {#if quotaMax !== null}
      <div
        style="margin-top: 8px; display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; font-size: 12px;"
      >
        <div>
          <small style="color: var(--muted);">{t("admin_cornllm_balance", {}, "CornLLM")}</small>
          <div><strong>{fmtUsd(quotaMax)}</strong></div>
        </div>
        <div>
          <small style="color: var(--muted);"
            >{t("admin_cornllm_balance_spent", {}, "Spent")}</small
          >
          <div><strong>{fmtUsd(quotaSpent)}</strong></div>
        </div>
        <div>
          <small style="color: var(--muted);">{t("wa_home_remaining", {}, "Remaining")}</small>
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
          {t("tg_hermes_logs_refresh_button", {}, "Refresh logs")}
        </Button>
        <pre
          style="margin-top: 8px; padding: 8px; background: var(--surface-subtle); border: 1px solid var(--surface-subtle-border); border-radius: 8px; font-family: ui-monospace, monospace; font-size: 11px; max-height: 240px; overflow: auto; white-space: pre-wrap; word-break: break-all;"
          >{logs || t("logs_empty", {}, "(empty)")}</pre>
      </div>
    {/if}
    {#if confirmRestart}
      <div
        style="margin-top: 10px; padding: 10px; border: 1px solid var(--border, #ccc); border-radius: 6px; background: var(--surface-subtle, #f7f7f7);"
      >
        <p style="margin: 0 0 6px; font-size: 13px;">
          {t(
            "wa_hermes_restart_confirm_inline",
            {},
            "Restart the bot? Container will stop and start again (~30 seconds)."
          )}
        </p>
        <div style="display: flex; gap: 8px; flex-wrap: wrap;">
          <Button variant="primary" onclick={confirmRestartAction} disabled={busy}>
            <RefreshCw size={14} class={busyAction === "restart" ? "spinning" : ""} />
            {t("wa_hermes_restart_confirm_button", {}, "Yes, restart")}
          </Button>
          <Button variant="secondary" onclick={cancelRestart} disabled={busy}
            >{t("cancel", {}, "Cancel")}</Button
          >
        </div>
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
