<script lang="ts">
  import { Input } from "$components/ui/index.js";
  import Dialog from "$components/ui/dialog.svelte";
  import { AdminButton, AdminField, AdminSelect } from "$components/patterns/admin/index.js";
  import PromoEffectSelector from "./PromoEffectSelector.svelte";
  import type { components } from "$lib/api/openapi.generated";

  type TranslateFn = (key: string, params?: Record<string, unknown>, fallback?: string) => string;
  type PromoDraft = Omit<components["schemas"]["PromoCreateBody"], "valid_days"> & {
    valid_days: number;
  };
  type CreateNumberField =
    | "bonus_days"
    | "discount_percent"
    | "duration_multiplier"
    | "traffic_multiplier"
    | "min_subscription_months"
    | "min_traffic_gb"
    | "max_activations"
    | "valid_days";
  type PromoEffectKind =
    "bonus_days" | "discount_percent" | "duration_multiplier" | "traffic_multiplier";
  type ScopeItem = { value: string; label: string };

  type Props = {
    at: TranslateFn;
    draft: PromoDraft;
    effectKind: PromoEffectKind;
    onBonusRequiresPaymentChange: (checked: boolean) => void;
    onClose: () => void;
    onCodeInput: (code: string) => void;
    onCreate: () => void | Promise<void>;
    onEffectChange: (value: string) => void;
    onNumberInput: (field: CreateNumberField, value: string) => void;
    onScopeChange: (scope: string) => void;
    open: boolean;
    scopeItems: ScopeItem[];
    usesCheckout: boolean;
  };

  let {
    at,
    draft,
    effectKind,
    onBonusRequiresPaymentChange,
    onClose,
    onCodeInput,
    onCreate,
    onEffectChange,
    onNumberInput,
    onScopeChange,
    open,
    scopeItems,
    usesCheckout,
  }: Props = $props();

  function inputValue(event: Event): string {
    return (event.currentTarget as HTMLInputElement).value;
  }
</script>

<Dialog
  {open}
  title={at("promo_create_title", {}, "Create code")}
  closeLabel={at("close", {}, "Close")}
  onclose={onClose}
  class="admin-dialog admin-dialog-compact admin-promo-dialog"
>
  <div class="admin-form" data-dialog-content>
    <div class="admin-dialog-form-section">
      <div class="admin-form-row-2">
        <AdminField label={at("promo_label_code", {}, "Code")}>
          <Input
            type="text"
            class="input"
            value={draft.code || ""}
            oninput={(event) => onCodeInput(inputValue(event))}
            placeholder="AUTO"
          />
        </AdminField>
        <AdminField label={at("promo_label_scope", {}, "Scope")}>
          <AdminSelect
            value={draft.applies_to || "all"}
            items={scopeItems}
            placeholder={at("promo_label_scope", {}, "Scope")}
            onValueChange={onScopeChange}
          />
        </AdminField>
      </div>
      <div class="admin-promo-config-block">
        <div class="admin-promo-block-head">
          <div class="admin-promo-block-title">
            <strong>{at("promo_col_effect", {}, "Effect")}</strong>
            <small>
              {at("promo_effect_single_hint", {}, "Choose one effect; values do not stack.")}
            </small>
          </div>
        </div>
        <PromoEffectSelector
          {at}
          value={effectKind}
          values={draft}
          bonusRequiresPayment={Boolean(draft.bonus_requires_payment)}
          onValueChange={onEffectChange}
          {onNumberInput}
          {onBonusRequiresPaymentChange}
        />
      </div>
      <div class="admin-promo-config-block">
        <div class="admin-promo-block-head">
          <div class="admin-promo-block-title">
            <strong>{at("promo_col_eligibility", {}, "Eligibility")}</strong>
            <small>
              {usesCheckout
                ? at(
                    "promo_conditions_hint",
                    {},
                    "Optional minimum purchase requirements checked before the code can be applied."
                  )
                : at(
                    "promo_conditions_disabled_for_instant_bonus",
                    {},
                    "Instant bonus-day grants do not use purchase requirements."
                  )}
            </small>
          </div>
        </div>
        <div class="admin-form-row-2">
          <AdminField label={at("promo_label_min_months", {}, "Min months")}>
            <Input
              type="number"
              class="input"
              min="1"
              disabled={!usesCheckout}
              value={draft.min_subscription_months == null
                ? ""
                : String(draft.min_subscription_months)}
              oninput={(event) => onNumberInput("min_subscription_months", inputValue(event))}
            />
          </AdminField>
          <AdminField label={at("promo_label_min_gb", {}, "Min GB")}>
            <Input
              type="number"
              class="input"
              min="0"
              step="0.01"
              disabled={!usesCheckout}
              value={draft.min_traffic_gb == null ? "" : String(draft.min_traffic_gb)}
              oninput={(event) => onNumberInput("min_traffic_gb", inputValue(event))}
            />
          </AdminField>
        </div>
      </div>
      <div class="admin-form-row-2">
        <AdminField label={at("promo_label_max_activations", {}, "Max uses")}>
          <Input
            type="number"
            class="input"
            min="1"
            value={String(draft.max_activations)}
            oninput={(event) => onNumberInput("max_activations", inputValue(event))}
          />
        </AdminField>
        <AdminField label={at("promo_label_valid_days", {}, "Valid days")}>
          <Input
            type="number"
            class="input"
            min="0"
            value={draft.valid_days ? String(draft.valid_days) : ""}
            oninput={(event) => onNumberInput("valid_days", inputValue(event))}
          />
        </AdminField>
      </div>
    </div>
    <div class="admin-dialog-actions">
      <AdminButton onclick={onClose}>{at("btn_cancel", {}, "Cancel")}</AdminButton>
      <AdminButton variant="primary" onclick={onCreate}>
        {at("btn_create", {}, "Create")}
      </AdminButton>
    </div>
  </div>
</Dialog>
