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
  }: { appSettings?: AnyRecord; subscription?: AnyRecord; apiUnchecked?: ApiUnchecked } = $props();

  const hermesMode = $derived(String(appSettings?.panel_write_mode || "") === "hermes");
  const active = $derived(Boolean(subscription?.active));
  // ponytail: the previous two-click confirmation (tap "Удалить" then
  // "Нажмите ещё раз") was too easy to trigger by accident — the
  // buttons sat side by side and a quick double-tap wiped the
  // tenant. Now the user must type the word "УДАЛИТЬ" before the
  // final Delete button enables, mirroring the Telegram bot's
  // "/delete" handler.
  const CONFIRMATION_PHRASE = "УДАЛИТЬ";
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
    if (!confirm("Приостановить бота? Ключ CornLLM будет заблокирован.")) return;
    busy = "suspend";
    error = null;
    try {
      await callApi("/tenant/suspend", "POST");
      info = "Бот приостановлен.";
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
      info = "Бот удалён.";
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
    <h3 style="margin: 0 0 8px; font-size: 15px; color: var(--danger);">⚠️ Опасная зона</h3>
    <p style="margin: 0 0 10px; color: var(--muted); font-size: 12px;">
      Приостановка блокирует контейнер и ключ CornLLM. Удаление останавливает контейнер; данные
      хранилища сохраняются 30 дней.
    </p>
    {#if !showDelete}
      <div style="display: flex; gap: 8px; flex-wrap: wrap;">
        <Button variant="secondary" onclick={suspend} disabled={busy !== "" || !actionsEnabled}
          >⏸ Приостановить</Button
        >
        <Button variant="danger" onclick={requestDelete} disabled={busy !== "" || !actionsEnabled}
          >🗑 Удалить бота</Button
        >
      </div>
    {:else}
      <div
        style="margin: 8px 0 0; padding: 10px; border: 1px solid var(--danger, #e74c3c); border-radius: 6px;"
      >
        <p style="margin: 0 0 6px; font-size: 12px; color: var(--muted);">
          Это действие нельзя отменить. Введите <b>{CONFIRMATION_PHRASE}</b> ниже, чтобы подтвердить.
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
            disabled={!deleteEnabled || busy !== ""}>⛔ Подтвердить удаление</Button
          >
          <Button variant="secondary" onclick={cancelDelete} disabled={busy !== ""}>Отмена</Button>
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
