<script lang="ts">
  import { Input } from "$components/ui/index.js";
  import { Trash2 } from "$components/ui/icons.js";
  import { getContext, onMount } from "svelte";
  import Dialog from "$components/ui/dialog.svelte";
  import {
    AdminBadge,
    AdminButton,
    AdminEmptyState,
    AdminField,
    AdminTable,
    AdminTableSkeleton,
  } from "$components/patterns/admin/index.js";
  import { TableHandler } from "@vincjo/datatables";
  import type { PromosStore } from "../../lib/admin/stores/promosStore";
  import type { components } from "../../lib/api/openapi.generated";

  type TranslateFn = (key: string, params?: Record<string, unknown>, fallback?: string) => string;
  type Promo = components["schemas"]["PromoOut"];
  type PromoDraft = components["schemas"]["PromoCreateBody"];

  let {
    at,
    fmtDateShort,
  }: {
    at: TranslateFn;
    fmtDateShort: (value: string) => string;
  } = $props();

  const promosStore = getContext<PromosStore>("promosStore");
  const promosTable = new TableHandler<Promo>();

  const promos = $derived(promosStore.promos as Promo[]);
  const promosTotal = $derived(Number(promosStore.promosTotal || 0));
  const promosPage = $derived(Number(promosStore.promosPage || 0));
  const promosLoading = $derived(Boolean(promosStore.promosLoading));
  const promoCreateOpen = $derived(Boolean(promosStore.promoCreateOpen));
  const promoDraft = $derived(
    (promosStore.promoDraft || {
      code: "",
      bonus_days: 7,
      discount_percent: null,
      duration_multiplier: null,
      traffic_multiplier: null,
      applies_to: "all",
      min_subscription_months: null,
      min_traffic_gb: null,
      max_activations: 1,
      valid_days: 30,
      origin: "admin",
    }) as PromoDraft
  );
  const promoRows = $derived(promosTable.rows as Promo[]);

  $effect(() => promosTable.setRows(promos));

  const promosHasMore = $derived(promos.length < promosTotal);
  const promoHeaders = $derived([
    at("promo_col_code", {}, "Code"),
    at("promo_col_effect", {}, "Effect"),
    at("promo_col_scope", {}, "Scope"),
    at("promo_col_activations", {}, "Uses"),
    at("promo_col_valid_until", {}, "Valid until"),
    at("promo_col_status", {}, "Status"),
    at("actions", {}, "Actions"),
  ]);

  onMount(() => {
    promosStore.loadPromos();
  });

  function nullableNumber(value: string): number | null {
    const trimmed = value.trim();
    if (!trimmed) return null;
    const parsed = Number(trimmed);
    return Number.isFinite(parsed) ? parsed : null;
  }

  function thresholdText(promo: Promo): string {
    const parts: string[] = [];
    if (promo.min_subscription_months) parts.push(`>=${promo.min_subscription_months} mo`);
    if (promo.min_traffic_gb) parts.push(`>=${promo.min_traffic_gb} GB`);
    return parts.join(", ");
  }
</script>

<div class="admin-table-wrap">
  {#if promosLoading}
    <AdminTableSkeleton
      headers={promoHeaders}
      rows={6}
      actionColumn
      widths={["92px", "92px", "72px", "64px", "96px", "72px", "92px"]}
    />
  {:else if !promos.length}
    <AdminEmptyState tone="card">
      <span class="admin-muted">{at("promos_empty", {}, "No codes")}</span>
    </AdminEmptyState>
  {:else}
    <AdminTable>
      <thead>
        <tr>
          <th>{at("promo_col_code", {}, "Code")}</th>
          <th>{at("promo_col_effect", {}, "Effect")}</th>
          <th>{at("promo_col_scope", {}, "Scope")}</th>
          <th>{at("promo_col_activations", {}, "Uses")}</th>
          <th>{at("promo_col_valid_until", {}, "Valid until")}</th>
          <th>{at("promo_col_status", {}, "Status")}</th>
          <th class="admin-cell-actions">{at("actions", {}, "Actions")}</th>
        </tr>
      </thead>
      <tbody>
        {#each promoRows as p (p.id)}
          <tr>
            <td class="admin-cell-mono" data-label={at("promo_col_code", {}, "Code")}>{p.code}</td>
            <td data-label={at("promo_col_effect", {}, "Effect")}>
              {p.effect_summary || `+${p.bonus_days} ${at("days_short", {}, "d")}`}
            </td>
            <td data-label={at("promo_col_scope", {}, "Scope")}>
              <AdminBadge variant="muted">{p.applies_to}</AdminBadge>
              {#if thresholdText(p)}
                <small class="admin-muted">{thresholdText(p)}</small>
              {/if}
            </td>
            <td data-label={at("promo_col_activations", {}, "Uses")}>
              {p.current_activations}/{p.max_activations}
            </td>
            <td data-label={at("promo_col_valid_until", {}, "Valid until")}>
              {p.valid_until ? fmtDateShort(p.valid_until) : "∞"}
            </td>
            <td data-label={at("promo_col_status", {}, "Status")}>
              {#if p.is_active}
                <AdminBadge variant="success">{at("status_active", {}, "Active")}</AdminBadge>
              {:else}
                <AdminBadge variant="muted">{at("status_disabled", {}, "Disabled")}</AdminBadge>
              {/if}
            </td>
            <td class="admin-cell-actions" data-label={at("actions", {}, "Actions")}>
              <AdminButton size="sm" onclick={() => promosStore.togglePromo(p)}>
                {p.is_active ? at("btn_disable", {}, "Off") : at("btn_enable", {}, "On")}
              </AdminButton>
              <AdminButton size="sm" variant="danger" onclick={() => promosStore.deletePromo(p)}>
                <Trash2 size={13} />
              </AdminButton>
            </td>
          </tr>
        {/each}
      </tbody>
    </AdminTable>
  {/if}
  {#if promosHasMore}
    <div style="padding: 12px; text-align: center;">
      <AdminButton onclick={() => promosStore.setPage(promosPage + 1)}>
        {at("btn_show_more", {}, "Show more")}
      </AdminButton>
    </div>
  {/if}
</div>

<Dialog
  open={promoCreateOpen}
  title={at("promo_create_title", {}, "Create code")}
  closeLabel={at("close", {}, "Close")}
  onclose={() => promosStore.setCreateOpen(false)}
  class="admin-dialog admin-dialog-compact"
>
  <div class="admin-form" data-dialog-content>
    <div class="admin-dialog-form-section">
      <AdminField label={at("promo_label_code", {}, "Code")}>
        <Input
          type="text"
          class="input"
          value={promoDraft.code || ""}
          oninput={(e) =>
            promosStore.updateDraft({ code: (e.currentTarget as HTMLInputElement).value })}
          placeholder="AUTO"
        />
      </AdminField>
      <AdminField label={at("promo_label_scope", {}, "Scope")}>
        <select
          class="input"
          value={promoDraft.applies_to || "all"}
          onchange={(e) =>
            promosStore.updateDraft({ applies_to: (e.currentTarget as HTMLSelectElement).value })}
        >
          <option value="all">all</option>
          <option value="subscription">subscription</option>
          <option value="traffic">traffic</option>
          <option value="traffic_topup">traffic_topup</option>
          <option value="hwid">hwid</option>
        </select>
      </AdminField>
    </div>
    <div class="admin-dialog-form-section">
      <div class="admin-form-row-2">
        <AdminField label={at("promo_label_bonus_days", {}, "Bonus days")}>
          <Input
            type="number"
            class="input"
            min="0"
            value={String(promoDraft.bonus_days || 0)}
            oninput={(e) =>
              promosStore.updateDraft({
                bonus_days: Number((e.currentTarget as HTMLInputElement).value),
              })}
          />
        </AdminField>
        <AdminField label={at("promo_label_discount", {}, "Discount %")}>
          <Input
            type="number"
            class="input"
            min="0"
            max="100"
            step="0.01"
            value={promoDraft.discount_percent == null ? "" : String(promoDraft.discount_percent)}
            oninput={(e) =>
              promosStore.updateDraft({
                discount_percent: nullableNumber((e.currentTarget as HTMLInputElement).value),
              })}
          />
        </AdminField>
      </div>
      <div class="admin-form-row-2">
        <AdminField label={at("promo_label_duration_multiplier", {}, "Duration x")}>
          <Input
            type="number"
            class="input"
            min="1"
            step="0.001"
            value={promoDraft.duration_multiplier == null
              ? ""
              : String(promoDraft.duration_multiplier)}
            oninput={(e) =>
              promosStore.updateDraft({
                duration_multiplier: nullableNumber((e.currentTarget as HTMLInputElement).value),
              })}
          />
        </AdminField>
        <AdminField label={at("promo_label_traffic_multiplier", {}, "Traffic x")}>
          <Input
            type="number"
            class="input"
            min="1"
            step="0.001"
            value={promoDraft.traffic_multiplier == null
              ? ""
              : String(promoDraft.traffic_multiplier)}
            oninput={(e) =>
              promosStore.updateDraft({
                traffic_multiplier: nullableNumber((e.currentTarget as HTMLInputElement).value),
              })}
          />
        </AdminField>
      </div>
      <div class="admin-form-row-2">
        <AdminField label={at("promo_label_min_months", {}, "Min months")}>
          <Input
            type="number"
            class="input"
            min="1"
            value={promoDraft.min_subscription_months == null
              ? ""
              : String(promoDraft.min_subscription_months)}
            oninput={(e) =>
              promosStore.updateDraft({
                min_subscription_months: nullableNumber(
                  (e.currentTarget as HTMLInputElement).value
                ),
              })}
          />
        </AdminField>
        <AdminField label={at("promo_label_min_gb", {}, "Min GB")}>
          <Input
            type="number"
            class="input"
            min="0"
            step="0.01"
            value={promoDraft.min_traffic_gb == null ? "" : String(promoDraft.min_traffic_gb)}
            oninput={(e) =>
              promosStore.updateDraft({
                min_traffic_gb: nullableNumber((e.currentTarget as HTMLInputElement).value),
              })}
          />
        </AdminField>
      </div>
      <div class="admin-form-row-2">
        <AdminField label={at("promo_label_max_activations", {}, "Max uses")}>
          <Input
            type="number"
            class="input"
            min="1"
            value={String(promoDraft.max_activations)}
            oninput={(e) =>
              promosStore.updateDraft({
                max_activations: Number((e.currentTarget as HTMLInputElement).value),
              })}
          />
        </AdminField>
        <AdminField label={at("promo_label_valid_days", {}, "Valid days")}>
          <Input
            type="number"
            class="input"
            min="1"
            value={String(promoDraft.valid_days)}
            oninput={(e) =>
              promosStore.updateDraft({
                valid_days: Number((e.currentTarget as HTMLInputElement).value),
              })}
          />
        </AdminField>
      </div>
    </div>
    <div class="admin-dialog-actions">
      <AdminButton onclick={() => promosStore.setCreateOpen(false)}>
        {at("btn_cancel", {}, "Cancel")}
      </AdminButton>
      <AdminButton variant="primary" onclick={promosStore.createPromo}>
        {at("btn_create", {}, "Create")}
      </AdminButton>
    </div>
  </div>
</Dialog>
