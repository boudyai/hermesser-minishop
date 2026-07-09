<script lang="ts">
  import Button from "$components/ui/button.svelte";
  import Card from "$components/ui/card.svelte";

  type AnyRecord = Record<string, any>;
  type ApiUnchecked = (
    path: string,
    options?: Parameters<typeof fetch>[1]
  ) => Promise<Record<string, unknown>>;
  const missingApi: ApiUnchecked = async () => ({ ok: false, error: "api_unavailable" });
  let {
    appSettings = {},
    subscription = {},
    apiUnchecked = missingApi,
    t = (key: string, _params?: AnyRecord, fallback?: string) => fallback || key,
  }: {
    appSettings?: AnyRecord;
    subscription?: AnyRecord;
    apiUnchecked?: ApiUnchecked;
    t?: (key: string, params?: AnyRecord, fallback?: string) => string;
  } = $props();

  const hermesMode = $derived(String(appSettings?.panel_write_mode || "") === "hermes");
  const active = $derived(Boolean(subscription?.active));
  // ponytail: the previous two-click confirmation (tap "Удалить" then
  // "Нажмите ещё раз") was too easy to trigger by accident — the
  // buttons sat side by side and a quick double-tap wiped the
  // tenant. Now the user must type the word "DELETE" before the
  // final Delete button enables, mirroring the Telegram bot's
  // "/delete" handler.
  const CONFIRMATION_PHRASE = "DELETE";
  // ponytail: the core rejects suspend/delete on tenants in
  // non-actionable states (deleting / deleted / archived) with a
  // 409. Gate the buttons here so the user doesn't see those
  // failures.
  const tenantStatus = $derived(
    String(subscription?.tenant_status || subscription?.status || "").toLowerCase()
  );
  const actionsEnabled = $derived(
    active && !["deleting", "deleted", "archived"].includes(tenantStatus)
  );

  let busy = $state<"suspend" | "delete" | "">("");
  let showDelete = $state(false);
  let deletePhrase = $state("");
  let error = $state<string | null>(null);
  let info = $state<string | null>(null);

  const deleteEnabled = $derived(deletePhrase.trim() === CONFIRMATION_PHRASE);

  async function callApi(path: string, method: string): Promise<unknown> {
    const data = await apiUnchecked(path, {
      method,
    });
    if (data.ok === false) {
      const code = String(data.error || "api_failed");
      throw new Error(code);
    }
    return data;
  }

  async function suspend() {
    if (
      !confirm(
        t(
          "wa_danger_suspend_confirm",
          {},
          "Suspend the bot? The CornLLM key will be blocked."
        )
      )
    )
      return;
    busy = "suspend";
    error = null;
    try {
      await callApi("/tenant/suspend", "POST");
      info = t("wa_danger_suspended", {}, "Bot suspended.");
      setTimeout(() => window.location.reload(), 1000);
    } catch (e) {
      error = e instanceof Error ? e.message : "Failed";
    } finally {
      busy = "";
    }
  }

  function requestDelete() {
    showDelete = true;
    deletePhrase = "";
    error = null;
  }

  function cancelDelete() {
    showDelete = false;
    deletePhrase = "";
  }

  async function confirmAndDelete() {
    if (!deleteEnabled) return;
    busy = "delete";
    error = null;
    try {
      await callApi("/tenant", "DELETE");
      info = t("wa_danger_deleted", {}, "Bot deleted.");
      setTimeout(() => window.location.reload(), 1000);
    } catch (e) {
      error = e instanceof Error ? e.message : "Failed";
    } finally {
      busy = "";
    }
  }
</script>

{#if hermesMode && active}
  <Card>
    <h3 style="margin: 0 0 8px; font-size: 15px; color: var(--danger);">
      {t("wa_danger_title", {}, "⚠️ Danger zone")}
    </h3>
    <p style="margin: 0 0 10px; color: var(--muted); font-size: 12px;">
      {t(
        "wa_danger_help",
        {},
        "Suspend blocks the container and starts a 7-day deletion countdown. To pause without deletion, use the Pause button above instead. Delete stops the container; volume data is kept for 30 days."
      )}
    </p>
    <p style="margin: 0 0 10px; color: var(--muted); font-size: 12px;">
      {t(
        "wa_danger_suspend_warning",
        {},
        "Suspend is destructive: 7-day auto-delete. Pause is safe — resume anytime."
      )}
    </p>
    {#if !showDelete}
      <div style="display: flex; gap: 8px; flex-wrap: wrap;">
        <Button variant="secondary" onclick={suspend} disabled={busy !== "" || !actionsEnabled}
          >{t("wa_danger_suspend", {}, "⏸ Suspend")}</Button
        >
        <Button variant="danger" onclick={requestDelete} disabled={busy !== "" || !actionsEnabled}
          >{t("wa_danger_delete", {}, "Delete bot")}</Button
        >
      </div>
    {:else}
      <div
        style="margin: 8px 0 0; padding: 10px; border: 1px solid var(--danger, #e74c3c); border-radius: 6px;"
      >
        <p style="margin: 0 0 6px; font-size: 12px; color: var(--muted);">
          {t(
            "wa_danger_confirm_help",
            { phrase: CONFIRMATION_PHRASE },
            `This cannot be undone. Type ${CONFIRMATION_PHRASE} below to confirm.`
          )}
        </p>
        <input
          type="text"
          bind:value={deletePhrase}
          placeholder={CONFIRMATION_PHRASE}
          autocomplete="off"
          spellcheck={false}
          style="width: 100%; padding: 6px 8px; box-sizing: border-box; border: 1px solid var(--border, #ccc); border-radius: 4px; font-family: monospace;"
        />
        <div style="display: flex; gap: 8px; margin-top: 8px; flex-wrap: wrap;">
          <Button
            variant="danger"
            onclick={confirmAndDelete}
            disabled={!deleteEnabled || busy !== ""}
            >{t("wa_danger_confirm", {}, "⛔ Confirm deletion")}</Button
          >
          <Button variant="secondary" onclick={cancelDelete} disabled={busy !== ""}
            >{t("wa_danger_cancel", {}, "Cancel")}</Button
          >
        </div>
      </div>
    {/if}
    {#if error}
      <p style="margin: 8px 0 0; color: var(--danger); font-size: 12px;">{error}</p>
    {/if}
    {#if info}
      <p style="margin: 8px 0 0; color: var(--muted); font-size: 12px;">{info}</p>
    {/if}
  </Card>
{/if}
