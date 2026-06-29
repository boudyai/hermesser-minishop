<script lang="ts">
  import { AdminField } from "$components/patterns/admin/index.js";
  import { Input, RadioGroup, RadioGroupItem } from "$components/ui/index.js";

  type TranslateFn = (key: string, params?: Record<string, unknown>, fallback?: string) => string;
  type PromoEffectKind =
    "bonus_days" | "discount_percent" | "duration_multiplier" | "traffic_multiplier";
  type EffectValues = {
    bonus_days?: number | null;
    discount_percent?: number | null;
    duration_multiplier?: number | null;
    traffic_multiplier?: number | null;
  };

  let {
    at,
    value,
    values,
    onValueChange,
    onNumberInput,
  }: {
    at: TranslateFn;
    value: PromoEffectKind;
    values: EffectValues;
    onValueChange: (value: string) => void;
    onNumberInput: (field: PromoEffectKind, value: string) => void;
  } = $props();

  const effectOptions = $derived([
    {
      kind: "bonus_days",
      title: at("promo_effect_bonus_days_title", {}, "Bonus days"),
      hint: at("promo_effect_bonus_days_hint", {}, "Adds days after a subscription payment."),
    },
    {
      kind: "discount_percent",
      title: at("promo_effect_discount_title", {}, "Discount"),
      hint: at("promo_effect_discount_hint", {}, "Reduces the checkout amount before payment."),
    },
    {
      kind: "duration_multiplier",
      title: at("promo_effect_duration_title", {}, "Duration multiplier"),
      hint: at("promo_effect_duration_hint", {}, "Multiplies paid subscription duration."),
    },
    {
      kind: "traffic_multiplier",
      title: at("promo_effect_traffic_title", {}, "Traffic multiplier"),
      hint: at(
        "promo_effect_traffic_hint",
        {},
        "Multiplies the traffic amount in a traffic purchase."
      ),
    },
  ] as Array<{ kind: PromoEffectKind; title: string; hint: string }>);

  function inputValue(event: Event): string {
    return (event.currentTarget as HTMLInputElement).value;
  }
</script>

<RadioGroup class="admin-promo-effect-options" {value} {onValueChange}>
  {#each effectOptions as option (option.kind)}
    <RadioGroupItem class="admin-promo-effect-card" value={option.kind} ariaLabel={option.title}>
      <span class="admin-promo-effect-copy">
        <strong>{option.title}</strong>
        <small>{option.hint}</small>
      </span>
    </RadioGroupItem>
  {/each}
</RadioGroup>

<div class="admin-promo-effect-value">
  {#if value === "bonus_days"}
    <AdminField label={at("promo_label_bonus_days", {}, "Bonus days")}>
      <Input
        type="number"
        class="input"
        min="1"
        value={String(values.bonus_days || 1)}
        oninput={(e) => onNumberInput("bonus_days", inputValue(e))}
      />
    </AdminField>
  {:else if value === "discount_percent"}
    <AdminField label={at("promo_label_discount", {}, "Discount %")}>
      <Input
        type="number"
        class="input"
        min="0.01"
        max="100"
        step="0.01"
        value={values.discount_percent == null ? "" : String(values.discount_percent)}
        oninput={(e) => onNumberInput("discount_percent", inputValue(e))}
      />
    </AdminField>
  {:else if value === "duration_multiplier"}
    <AdminField label={at("promo_label_duration_multiplier", {}, "Duration x")}>
      <Input
        type="number"
        class="input"
        min="1.001"
        step="0.001"
        value={values.duration_multiplier == null ? "" : String(values.duration_multiplier)}
        oninput={(e) => onNumberInput("duration_multiplier", inputValue(e))}
      />
    </AdminField>
  {:else}
    <AdminField label={at("promo_label_traffic_multiplier", {}, "Traffic x")}>
      <Input
        type="number"
        class="input"
        min="1.001"
        step="0.001"
        value={values.traffic_multiplier == null ? "" : String(values.traffic_multiplier)}
        oninput={(e) => onNumberInput("traffic_multiplier", inputValue(e))}
      />
    </AdminField>
  {/if}
</div>

<style>
  :global(.ui-radio-group.admin-promo-effect-options) {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 10px;
  }

  :global(.ui-radio-item.admin-promo-effect-card) {
    display: flex;
    align-items: flex-start;
    justify-content: flex-start;
    width: 100%;
    height: auto;
    min-height: 92px;
    gap: 10px;
    padding: 12px;
    border-radius: 8px;
    background: var(--admin-surface-2);
    text-align: left;
  }

  :global(.ui-radio-item.admin-promo-effect-card:hover),
  :global(.ui-radio-item.admin-promo-effect-card[data-state="checked"]) {
    border-color: var(--accent);
  }

  :global(.ui-radio-item.admin-promo-effect-card[data-state="checked"]) {
    background: color-mix(in srgb, var(--accent) 9%, var(--admin-surface-2));
  }

  .admin-promo-effect-copy {
    display: grid;
    gap: 4px;
    min-width: 0;
  }

  .admin-promo-effect-copy strong {
    color: var(--admin-text);
    font-size: 13px;
    line-height: 1.2;
  }

  .admin-promo-effect-copy small {
    color: var(--admin-muted);
    font-size: 12px;
    line-height: 1.35;
  }

  .admin-promo-effect-value {
    max-width: 360px;
  }

  @media (max-width: 720px) {
    :global(.ui-radio-group.admin-promo-effect-options) {
      grid-template-columns: 1fr;
    }

    .admin-promo-effect-value {
      max-width: none;
    }
  }
</style>
