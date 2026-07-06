<script lang="ts">
  import Button from "$components/ui/button.svelte";
  import Card from "$components/ui/card.svelte";
  import Dialog from "$components/ui/dialog.svelte";
  import PaymentMethodGrid from "$lib/components/patterns/webapp/PaymentMethodGrid.svelte";
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
    t = (key: string, _params?: AnyRecord, fallback?: string) => fallback || key,
  }: {
    subscription?: AnyRecord;
    appSettings?: AnyRecord;
    apiUnchecked?: ApiUnchecked;
    paymentMethods?: AnyRecord[];
    selectedMethod?: string;
    t?: (key: string, params?: AnyRecord, fallback?: string) => string;
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
  let localMethod = $state<string>(selectedMethod);
  let busy = $state(false);
  let error = $state<string | null>(null);

  // ponytail: derived preview of what the typed-but-unblurred input will
  // resolve to on submit. The submit() function re-parses on click, but
  // showing the live preview avoids the "I typed 250 and the button still
  // says 300" confusion. Returns null when the input is empty (so the
  // user sees the currently-picked quick amount instead).
  const customParsed = $derived.by(() => {
    const raw = customAmount.replace(",", ".").trim();
    if (!raw) return null;
    const n = Number(raw);
    return Number.isFinite(n) ? Math.round(n) : null;
  });
  const submitAmount = $derived(customParsed !== null ? customParsed : amountRub);
  const submitAmountValid = $derived(submitAmount >= MIN_RUB);

  const enabledMethods = $derived(
    (paymentMethods || []).filter((m) => m && !m.disabled && typeof m.id === "string" && m.id)
  );

  // ponytail: when the card opens or the parent flips selectedMethod,
  // mirror it into local state so PaymentMethodGrid stays in sync.
  // The first enabled method is a safe default if the parent passed
  // an empty string — this keeps the dialog submittable even when
  // the user lands here without a payment-method selection upstream.
  $effect(() => {
    if (open) {
      if (selectedMethod) {
        localMethod = selectedMethod;
      } else if (!localMethod && enabledMethods.length > 0) {
        localMethod = enabledMethods[0].id;
      }
    }
  });

  function pickQuick(rub: number) {
    customAmount = "";
    amountRub = rub;
  }

  // ponytail: no oninput commit. The previous version committed on every
  // keystroke and would reset amountRub when the user typed a value
  // smaller than MIN_RUB (e.g. typing "1500" passes through "1" → "15"
  // → "150" → "1500", each step potentially resetting the submit target).
  // Now commit only on blur; submit() re-parses fresh from customAmount.

  async function submit() {
    if (!localMethod) {
      error = t("wa_topup_pick_method", {}, "Pick a payment method");
      return;
    }
    // ponytail: always re-parse on submit so the typed-but-unblurred
    // value reaches the API instead of the previously-picked quick amount.
    const raw = customAmount.replace(",", ".").trim();
    const submitted = raw ? Math.round(Number(raw)) : amountRub;
    if (!Number.isFinite(submitted) || submitted <= 0) {
      error = t("wa_topup_invalid_amount", {}, "Enter a valid amount");
      return;
    }
    if (submitted < MIN_RUB) {
      error = t("wa_topup_minimum", { minimum: MIN_RUB }, `Minimum ${MIN_RUB} ₽`);
      return;
    }
    amountRub = submitted;
    busy = true;
    error = null;
    try {
      // ponytail: apiBase is already "/api" so the client prefixes
      // every call. The previous hardcoded "/api/cornllm/topup"
      // collapsed to "/api/api/cornllm/topup" → 404. Pass the bare
      // path; the typed ApiClient adds the prefix.
      const data = (await apiUnchecked("/cornllm/topup", {
        method: "POST",
        body: JSON.stringify({
          amount_rub: amountRub,
          method: localMethod,
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
      error = null;
      open = false;
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
        <span>{t("admin_cornllm_balance", {}, "CornLLM")}</span>
      </div>
      <Button variant="primary" onclick={() => (open = true)} disabled={busy || !actionsEnabled}>
        <Plus size={14} />
        {t("wa_topup_action", {}, "Top up")}
      </Button>
    </div>
  </Card>
  <Dialog
    {open}
    title={t("wa_topup_cornllm_title", {}, "Top up CornLLM")}
    description={t(
      "wa_topup_cornllm_description",
      {},
      "1 USD = 100 ₽. The amount is credited to your bot's LiteLLM key right after payment."
    )}
    closeLabel={t("wa_topup_close", {}, "Close")}
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
        <span style="color: var(--muted);"
          >{t("wa_topup_custom_label", { minimum: MIN_RUB }, `Custom amount (min ${MIN_RUB} ₽)`)}</span
        >
        <input
          type="number"
          min={MIN_RUB}
          step={1}
          bind:value={customAmount}
          placeholder={t("wa_topup_custom_placeholder", {}, "e.g. 250")}
          style="padding: 8px; border: 1px solid var(--border, #ccc); border-radius: 4px; font-size: 14px;"
        />
        {#if customParsed !== null}
          <span style="color: var(--muted); font-size: 11px;">
            {submitAmountValid ? "→" : "✗"} {submitAmount} ₽{#if !submitAmountValid} {t("wa_topup_below_minimum_hint", { minimum: MIN_RUB })} {/if}
          </span>
        {/if}
      </label>
      <p style="margin: 0; font-size: 12px; color: var(--muted);">
        {t("wa_topup_payment_method_label", {}, "Payment method")}
      </p>
      <PaymentMethodGrid
        methods={enabledMethods}
        selectedMethod={localMethod}
        onSelect={(id) => (localMethod = id)}
      />
      {#if error}
        <p style="margin: 0; color: var(--danger); font-size: 12px;">{error}</p>
      {/if}
      <Button variant="primary" onclick={submit} disabled={busy || !actionsEnabled || !submitAmountValid}>
        {t("wa_topup_action_button", { amount: submitAmount }, `Top up ${submitAmount} ₽`)}
      </Button>
    </div>
  </Dialog>
{/if}
