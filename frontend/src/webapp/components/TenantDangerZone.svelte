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

  let busy = $state<"suspend" | "delete" | "">("");
  let confirmDelete = $state(false);
  let error = $state<string | null>(null);
  let info = $state<string | null>(null);

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
    if (!confirm("Приостановить бота? LiteLLM-ключ будет заблокирован.")) return;
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

  async function deleteAgent() {
    if (!confirmDelete) {
      confirmDelete = true;
      setTimeout(() => (confirmDelete = false), 10000);
      return;
    }
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
      Приостановка блокирует контейнер и LiteLLM-ключ. Удаление остановит контейнер и очистит его
      через 30 дней.
    </p>
    <div style="display: flex; gap: 8px; flex-wrap: wrap;">
      <Button variant="secondary" onclick={suspend} disabled={busy !== ""}>⏸ Приостановить</Button>
      <Button
        variant="danger"
        onclick={deleteAgent}
        disabled={busy !== ""}
        style={confirmDelete ? "background: #b91c1c; color: white;" : ""}
      >
        {confirmDelete ? "⚠️ Нажмите ещё раз для подтверждения" : "🗑 Удалить бота"}
      </Button>
    </div>
    {#if error}
      <p style="margin: 8px 0 0; color: var(--danger); font-size: 12px;">{error}</p>
    {/if}
    {#if info}
      <p style="margin: 8px 0 0; color: var(--muted); font-size: 12px;">{info}</p>
    {/if}
  </Card>
{/if}
