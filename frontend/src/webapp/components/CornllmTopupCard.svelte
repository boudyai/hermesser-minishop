<script lang="ts">
  import Button from "$components/ui/button.svelte";
  import Card from "$components/ui/card.svelte";
  import Dialog from "$components/ui/dialog.svelte";
  import { Plus } from "$components/ui/icons.js";

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
    paymentMethods = [],
    selectedMethod = "",
  }: {
    subscription?: AnyRecord;
    appSettings?: AnyRecord;
    apiUnchecked?: ApiUnchecked;
    paymentMethods?: AnyRecord[];
    selectedMethod?: string;
  } = $props();

  const hermesMode = $derived(String(appSettings?.panel_write_mode || "") === "hermes");
  const active = $derived(Boolean(subscription?.active));
  const tenantStatus = $derived(
    String(subscription?.tenant_status || subscription?.status || "").toLowerCase()
  );
  const actionsEnabled = $derived(
    active && !["deleting", "deleted", "archived", "suspended"].includes(tenantStatus)
  );

  const MIN_RUB = 100;
  const QUICK_RUB = [100, 300, 500, 1000];

  let open = $state(false);
  let amountRub = $state<number>(300);
  let customAmount = $state<string>("");
  let busy = $state(false);
  let error = $state<string | null>(null);

  function pickQuick(rub: number) {
    customAmount = "";
    amountRub = rub;
  }

  function commitCustom() {
    const parsed = Number(customAmount.replace(",", "."));
    if (Number.isFinite(parsed) && parsed >= MIN_RUB) amountRub = Math.round(parsed);
  }

  async function submit() {
    if (!selectedMethod) {
      error = "Выберите способ оплаты";
      return;
    }
    if (!Number.isFinite(amountRub) || amountRub < MIN_RUB) {
      error = `Минимум ${MIN_RUB} ₽`;
      return;
    }
    busy = true;
    error = null;
    try {
      const data = (await apiUnchecked("/api/cornllm/topup", {
        method: "POST",
        body: JSON.stringify({
          amount_rub: amountRub,
          method: selectedMethod,
        }),
      })) as Record<string, unknown>;
      if (data?.ok === false) {
        throw new Error(String((data as { error?: string }).error || "topup_create_failed"));
      }
      // ponytail: provider returns { payment_url, payment_id, ... }
      // — same shape as the subscription webapp flow. Reuse the
      // existing handler in AppModeContent that opens hosted
      // payment links / Telegram invoices. The provider reply is
      // already a JsonResponse envelope.
      const paymentUrl = (data as { payment_url?: string }).payment_url;
      if (paymentUrl && typeof window !== "undefined") {
        window.location.href = paymentUrl;
        return;
      }
      const action = String((data as { action?: string }).action || "");
      const paymentId = (data as { payment_id?: string | number }).payment_id;
      // No direct URL — the provider will send an invoice (Telegram
      // Stars / WATA). We don't know how to open it from this card
      // without a router to AppModeContent's handler; the user
      // will see the new pending payment in the next render of the
      // Home screen's status block.
      error = null;
      open = false;
      if (action === "open_invoice" && paymentId) {
        // The user will see "Telegram invoice sent" via the status card.
        // Nothing else to do here; the poll picks it up.
      }
    } catch (e) {
      error = e instanceof Error ? e.message : "topup_create_failed";
    } finally {
      busy = false;
    }
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
        <Plus size={15} />
        <span>Баланс CornLLM</span>
      </div>
      <Button
        variant="primary"
        onclick={() => (open = true)}
        disabled={busy || !actionsEnabled}
      >
        <Plus size={14} />
        Пополнить
      </Button>
    </div>
  </Card>
  <Dialog
    open={open}
    title="Пополнить CornLLM"
    description="1 USD = 100 ₽. Сумма зачисляется на баланс ключа LiteLLM бота сразу после оплаты."
    closeLabel="Закрыть"
    onclose={() => (open = false)}
  >
    <div style="display: flex; flex-direction: column; gap: 10px;">
      <div style="display: flex; gap: 6px; flex-wrap: wrap;">
        {#each QUICK_RUB as rub}
          <Button
            variant={amountRub === rub && !customAmount ? "primary" : "secondary"}
            onclick={() => pickQuick(rub)}
          >
            {rub} ₽
          </Button>
        {/each}
      </div>
      <label style="display: flex; flex-direction: column; gap: 4px; font-size: 12px;">
        <span style="color: var(--muted);">Своя сумма (от {MIN_RUB} ₽)</span>
        <input
          type="number"
          min={MIN_RUB}
          step={1}
          bind:value={customAmount}
          onblur={commitCustom}
          placeholder="например, 250"
          style="padding: 8px; border: 1px solid var(--border, #ccc); border-radius: 4px; font-size: 14px;"
        />
      </label>
      <p style="margin: 0; font-size: 12px; color: var(--muted);">
        Способ оплаты: <strong>{selectedMethod || "не выбран"}</strong>
      </p>
      {#if error}
        <p style="margin: 0; color: var(--danger); font-size: 12px;">{error}</p>
      {/if}
      <Button variant="primary" onclick={submit} disabled={busy || !actionsEnabled}>
        Пополнить на {amountRub} ₽
      </Button>
    </div>
  </Dialog>
{/if}
