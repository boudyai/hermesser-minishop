<script>
  import {
    ChevronRight,
    RefreshCw,
    Trash2,
    Plus,
    Save,
    TriangleAlert,
    X,
  } from "$components/ui/icons.js";
  import { getContext, onMount } from "svelte";
  import {
    AdminBadge,
    AdminButton,
    AdminEmptyState,
    AdminSelect,
  } from "$components/patterns/admin/index.js";
  import { Accordion, Switch } from "$components/ui/primitives.js";

  export let at;
  export let fmtMoney;
  export let onSettingsSaved = () => {};

  const tariffsStore = getContext("tariffsStore");
  const settingsStore = getContext("settingsStore");

  const TRIAL_SETTING_KEYS = [
    "TRIAL_ENABLED",
    "TRIAL_DURATION_DAYS",
    "TRIAL_TRAFFIC_LIMIT_GB",
    "TRIAL_TRAFFIC_STRATEGY",
    "TRIAL_SQUAD_UUIDS",
  ];
  const LEGACY_PERIODS = [
    ["1", "MONTH_1_ENABLED", "RUB_PRICE_1_MONTH", "STARS_PRICE_1_MONTH"],
    ["3", "MONTH_3_ENABLED", "RUB_PRICE_3_MONTHS", "STARS_PRICE_3_MONTHS"],
    ["6", "MONTH_6_ENABLED", "RUB_PRICE_6_MONTHS", "STARS_PRICE_6_MONTHS"],
    ["12", "MONTH_12_ENABLED", "RUB_PRICE_12_MONTHS", "STARS_PRICE_12_MONTHS"],
  ];
  const LEGACY_TARIFF_SETTING_KEYS = [
    ...LEGACY_PERIODS.flatMap((row) => row.slice(1)),
    "TRAFFIC_PACKAGES",
    "STARS_TRAFFIC_PACKAGES",
  ];
  const TRAFFIC_STRATEGY_OPTIONS = [
    { value: "NO_RESET", label: "NO_RESET" },
    { value: "DAY", label: "DAY" },
    { value: "WEEK", label: "WEEK" },
    { value: "MONTH", label: "MONTH" },
  ];

  $: ({
    tariffsCatalog,
    tariffsLoading,
    tariffsPath,
    tariffsSaving,
    panelSquads,
    panelSquadsLoading,
  } = $tariffsStore);
  $: ({ settingsSections, settingsDirty, settingsSaving } = $settingsStore);

  $: enabledTariffs = (tariffsCatalog.tariffs || []).filter((tariff) => tariff.enabled !== false);
  $: disabledTariffs = Math.max(0, (tariffsCatalog.tariffs || []).length - enabledTariffs.length);
  $: settingsFieldMap = new Map(
    (settingsSections || [])
      .flatMap((section) => section.fields || [])
      .map((field) => [field.key, field])
  );
  $: trialDirtyCount = TRIAL_SETTING_KEYS.filter((key) => Boolean(settingsDirty[key])).length;
  $: legacyDirtyCount = LEGACY_TARIFF_SETTING_KEYS.filter((key) =>
    Boolean(settingsDirty[key])
  ).length;
  $: panelSquadOptions = (panelSquads || []).map((squad) => ({
    value: squad.uuid,
    label: `${squad.name || squad.uuid} · ${String(squad.uuid || "").slice(0, 8)}...`,
  }));

  let selectedTrialSquad = "";
  let tariffSettingsOpen = [];

  function tariffName(tariff) {
    return tariff?.names?.ru || tariff?.names?.en || tariff?.key || "—";
  }

  function tariffPriceSummary(tariff) {
    if (tariff.billing_model === "traffic") {
      const rub = tariff.traffic_packages?.rub || [];
      const first = rub[0];
      return first
        ? `${first.gb} GB ${at("at", {}, "за")} ${fmtMoney(first.price, "RUB")}`
        : at("tariff_traffic_packages", {}, "Пакеты трафика");
    }
    const months = [...(tariff.enabled_periods || [])].sort((a, b) => a - b);
    return months
      .map((month) => {
        const rub = tariff.prices_rub?.[String(month)];
        const stars = tariff.prices_stars?.[String(month)];
        if (rub) return `${month} ${at("months_short", {}, "мес.")} ${fmtMoney(rub, "RUB")}`;
        if (stars) return `${month} ${at("months_short", {}, "мес.")} ${stars} ⭐`;
        return `${month} ${at("months_short", {}, "мес.")}`;
      })
      .join(" · ");
  }

  function fieldFor(key) {
    return settingsFieldMap.get(key) || { key, value: "" };
  }

  function valueForKey(key) {
    if (settingsDirty[key]?.deleted) return "";
    if (Object.prototype.hasOwnProperty.call(settingsDirty, key)) {
      return settingsDirty[key].value;
    }
    return fieldFor(key).value ?? "";
  }

  function boolValue(key) {
    return Boolean(valueForKey(key));
  }

  function setSetting(key, value) {
    settingsStore.markDirty(key, value);
  }

  function csvList(key) {
    return String(valueForKey(key) || "")
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean);
  }

  function setCsvList(key, values) {
    const normalized = Array.from(
      new Set((values || []).map((item) => String(item).trim()).filter(Boolean))
    );
    settingsStore.markDirty(key, normalized.join(","));
  }

  function addTrialSquad(uuid) {
    const next = String(uuid || "").trim();
    if (!next) return;
    setCsvList("TRIAL_SQUAD_UUIDS", [...csvList("TRIAL_SQUAD_UUIDS"), next]);
    selectedTrialSquad = "";
  }

  function removeTrialSquad(uuid) {
    setCsvList(
      "TRIAL_SQUAD_UUIDS",
      csvList("TRIAL_SQUAD_UUIDS").filter((item) => item !== uuid)
    );
  }

  function trialSquadLabel(uuid) {
    return tariffsStore.squadLabel(uuid);
  }

  async function saveTariffSettings() {
    await settingsStore.saveSettings(onSettingsSaved);
  }

  onMount(() => {
    tariffsStore.loadTariffs();
    settingsStore.loadSettings();
  });
</script>

{#if tariffsLoading}
  <AdminEmptyState>{at("loading", {}, "Загрузка…")}</AdminEmptyState>
{:else}
  <div class="admin-stat-grid">
    <div class="admin-stat-card">
      <span class="admin-stat-label">{at("tariffs_stat_total", {}, "Всего тарифов")}</span>
      <strong class="admin-stat-value">{tariffsCatalog.tariffs.length}</strong>
      <span class="admin-stat-trend"
        >{at("tariffs_stat_enabled", {}, "Включено")}: {enabledTariffs.length}</span
      >
    </div>
    <div class="admin-stat-card">
      <span class="admin-stat-label">{at("tariffs_stat_default", {}, "По умолчанию")}</span>
      <strong class="admin-stat-value">{tariffsCatalog.default_tariff || "—"}</strong>
      <span class="admin-stat-trend"
        >{at("tariffs_stat_default_hint", {}, "Используется для новых подписок")}</span
      >
    </div>
    <div class="admin-stat-card">
      <span class="admin-stat-label">{at("tariffs_stat_disabled", {}, "Отключено")}</span>
      <strong class="admin-stat-value">{disabledTariffs}</strong>
      <span class="admin-stat-trend"
        >{at("tariffs_stat_disabled_hint", {}, "Скрыто с витрины")}</span
      >
    </div>
  </div>

  <article class="admin-card admin-tariff-settings-card">
    <header class="admin-card-head">
      <div>
        <h3>{at("tariffs_trial_title", {}, "Trial access")}</h3>
        <small>
          {at(
            "tariffs_trial_subtitle",
            {},
            "Configure trial duration, traffic limit, and Remnawave squads from the tariff page."
          )}
        </small>
      </div>
      <div class="admin-editor-section-actions">
        <AdminBadge variant={boolValue("TRIAL_ENABLED") ? "success" : "muted"}>
          {boolValue("TRIAL_ENABLED")
            ? at("enabled", {}, "Enabled")
            : at("disabled", {}, "Disabled")}
        </AdminBadge>
        {#if trialDirtyCount}
          <AdminBadge variant="warning">
            {at("settings_dirty_count", { count: trialDirtyCount }, `Changes: ${trialDirtyCount}`)}
          </AdminBadge>
          <AdminButton
            size="sm"
            variant="primary"
            onclick={saveTariffSettings}
            disabled={settingsSaving}
          >
            <Save size={13} />
            {settingsSaving ? at("btn_saving", {}, "Saving...") : at("btn_save", {}, "Save")}
          </AdminButton>
        {/if}
      </div>
    </header>
    <div class="admin-card-body">
      <div class="admin-form admin-tariff-settings-form">
        <div class="admin-form-row admin-form-row-3">
          <label class="admin-field-label admin-field-label-compact">
            <span>{at("tariffs_trial_enabled", {}, "Trial enabled")}</span>
            <div class="admin-setting-switch">
              <Switch.Root
                checked={boolValue("TRIAL_ENABLED")}
                onCheckedChange={(checked) => setSetting("TRIAL_ENABLED", checked)}
                class="admin-switch-root"
              >
                <Switch.Thumb class="admin-switch-thumb" />
              </Switch.Root>
              <small
                >{boolValue("TRIAL_ENABLED")
                  ? at("enabled", {}, "Enabled")
                  : at("disabled", {}, "Disabled")}</small
              >
            </div>
          </label>
          <label class="admin-field-label admin-field-label-compact">
            <span>{at("tariffs_trial_days", {}, "Duration, days")}</span>
            <input
              class="input"
              type="number"
              min="0"
              step="1"
              value={valueForKey("TRIAL_DURATION_DAYS")}
              oninput={(event) => setSetting("TRIAL_DURATION_DAYS", event.currentTarget.value)}
            />
          </label>
          <label class="admin-field-label admin-field-label-compact">
            <span>{at("tariffs_trial_traffic", {}, "Traffic limit, GB")}</span>
            <input
              class="input"
              type="number"
              min="0"
              step="0.1"
              value={valueForKey("TRIAL_TRAFFIC_LIMIT_GB")}
              oninput={(event) => setSetting("TRIAL_TRAFFIC_LIMIT_GB", event.currentTarget.value)}
            />
          </label>
        </div>
        <div class="admin-form-row admin-form-row-2">
          <label class="admin-field-label admin-field-label-compact">
            <span>{at("tariffs_trial_strategy", {}, "Traffic reset strategy")}</span>
            <AdminSelect
              class="admin-setting-select"
              value={String(valueForKey("TRIAL_TRAFFIC_STRATEGY") || "NO_RESET")}
              items={TRAFFIC_STRATEGY_OPTIONS}
              ariaLabel={at("tariffs_trial_strategy", {}, "Traffic reset strategy")}
              onValueChange={(value) => setSetting("TRIAL_TRAFFIC_STRATEGY", value)}
            />
          </label>
          <label class="admin-field-label admin-field-label-compact">
            <span>{at("tariffs_trial_squads", {}, "Trial Internal Squads")}</span>
            <small>
              {at(
                "tariffs_trial_squads_hint",
                {},
                "These squads are applied when trial is activated. Empty value falls back to USER_SQUAD_UUIDS."
              )}
            </small>
            <AdminSelect
              bind:value={selectedTrialSquad}
              items={panelSquadOptions}
              disabled={panelSquadsLoading || !panelSquadOptions.length}
              placeholder={panelSquadsLoading
                ? at("loading", {}, "Loading...")
                : at("tariffs_trial_add_squad", {}, "Add squad from panel")}
              ariaLabel={at("tariffs_trial_add_squad", {}, "Add squad from panel")}
              onValueChange={addTrialSquad}
            />
            <input
              class="input"
              type="text"
              placeholder={valueForKey("USER_SQUAD_UUIDS") || "uuid-a,uuid-b"}
              value={valueForKey("TRIAL_SQUAD_UUIDS")}
              oninput={(event) => setSetting("TRIAL_SQUAD_UUIDS", event.currentTarget.value)}
            />
            <div class="admin-chip-list">
              {#each csvList("TRIAL_SQUAD_UUIDS") as uuid}
                <button type="button" class="admin-chip" onclick={() => removeTrialSquad(uuid)}>
                  {trialSquadLabel(uuid)}
                  <X size={12} />
                </button>
              {/each}
            </div>
          </label>
        </div>
      </div>
    </div>
  </article>

  <article class="admin-card">
    <header class="admin-card-head">
      <div>
        <h3>{at("tariffs_title", {}, "Каталог тарифов")}</h3>
        <small>{tariffsPath || "data/tariffs.json"}</small>
      </div>
      <div class="admin-editor-section-actions">
        <AdminButton
          size="sm"
          onclick={tariffsStore.loadTariffs}
          disabled={tariffsLoading || tariffsSaving}
        >
          <RefreshCw size={13} />
          {at("btn_refresh", {}, "Обновить")}
        </AdminButton>
        <AdminButton
          size="sm"
          variant="primary"
          onclick={tariffsStore.openCreateTariff}
          disabled={tariffsLoading || tariffsSaving}
        >
          <Plus size={13} />
          {at("btn_create_tariff", {}, "Создать тариф")}
        </AdminButton>
      </div>
    </header>
    <div class="admin-card-body">
      {#if !tariffsCatalog.tariffs.length}
        <AdminEmptyState>
          {at(
            "tariffs_catalog_empty",
            {},
            "Каталог пуст. Добавьте первый тариф, после сохранения будет создан JSON-файл каталога."
          )}
        </AdminEmptyState>
      {:else}
        <div class="admin-tariff-grid">
          {#each tariffsCatalog.tariffs as tariff}
            <article class="admin-tariff-card" class:is-disabled={tariff.enabled === false}>
              <div class="admin-tariff-top">
                <div>
                  <div class="admin-tariff-title">
                    <strong>{tariffName(tariff)}</strong>
                    {#if tariff.key === tariffsCatalog.default_tariff}
                      <AdminBadge variant="success"
                        >{at("status_default", {}, "Default")}</AdminBadge
                      >
                    {/if}
                  </div>
                  <code>{tariff.key}</code>
                </div>
                {#if tariff.enabled === false}
                  <AdminBadge variant="muted">{at("status_disabled", {}, "Выключен")}</AdminBadge>
                {:else}
                  <AdminBadge variant="success">{at("status_active", {}, "Активен")}</AdminBadge>
                {/if}
              </div>
              <p>
                {tariff.descriptions?.ru ||
                  tariff.descriptions?.en ||
                  at("no_description", {}, "Без описания")}
              </p>
              <div class="admin-tariff-facts">
                <span
                  >{tariff.billing_model === "traffic"
                    ? at("tariff_model_traffic", {}, "Трафик")
                    : at("tariff_model_periods", {}, "Периоды")}</span
                >
                <span>{tariffPriceSummary(tariff)}</span>
                <span>{at("tariff_squads", {}, "Squads")}: {(tariff.squad_uuids || []).length}</span
                >
                <span
                  >{at("tariff_premium", {}, "Premium")}: {(tariff.premium_squad_uuids || []).length
                    ? `${tariff.premium_monthly_gb || 0} GB`
                    : "—"}</span
                >
                <span
                  >{at("tariff_devices", {}, "Устройства")}: {tariff.hwid_device_limit ??
                    "env"}</span
                >
              </div>
              <div class="admin-tariff-actions">
                <AdminButton size="sm" onclick={() => tariffsStore.openEditTariff(tariff)}>
                  {at("btn_configure", {}, "Настроить")}
                </AdminButton>
                <AdminButton
                  size="sm"
                  onclick={() => tariffsStore.toggleTariffEnabled(tariff)}
                  disabled={tariffsSaving}
                >
                  {tariff.enabled === false
                    ? at("btn_enable", {}, "Включить")
                    : at("btn_disable", {}, "Выключить")}
                </AdminButton>
                <AdminButton
                  size="sm"
                  onclick={() => tariffsStore.setDefaultTariff(tariff.key)}
                  disabled={tariffsSaving ||
                    tariff.enabled === false ||
                    tariff.key === tariffsCatalog.default_tariff}
                >
                  {at("btn_set_default", {}, "По умолчанию")}
                </AdminButton>
                <AdminButton
                  size="sm"
                  variant="danger"
                  onclick={() =>
                    tariffsStore.updateState({
                      tariffDeleteTarget: tariff,
                      tariffDeleteOpen: true,
                    })}
                  disabled={tariffsSaving}
                  aria-label={at("btn_delete_tariff", {}, "Удалить тариф")}
                >
                  <Trash2 size={13} />
                </AdminButton>
              </div>
            </article>
          {/each}
        </div>
      {/if}
    </div>
  </article>

  <Accordion.Root
    type="multiple"
    bind:value={tariffSettingsOpen}
    class="admin-accordion admin-tariff-settings-accordion"
  >
    <Accordion.Item
      value="legacy-tariffs"
      class="admin-accordion-item admin-card admin-tariff-settings-card"
    >
      <Accordion.Header class="admin-accordion-header">
        <Accordion.Trigger class="admin-accordion-trigger">
          <span class="admin-accordion-title">
            {at("tariffs_legacy_title", {}, "Совместимость с legacy-тарифами")}
          </span>
          <span class="admin-accordion-meta">
            {at(
              "tariffs_legacy_subtitle",
              {},
              "Старые периоды и пакеты трафика remnawave-tg-shop, которые используются только без JSON-каталога."
            )}{#if legacyDirtyCount}
              · {at(
                "settings_dirty_count",
                { count: legacyDirtyCount },
                `Изменений: ${legacyDirtyCount}`
              )}{/if}
          </span>
          <ChevronRight size={16} class="admin-accordion-chev" />
        </Accordion.Trigger>
      </Accordion.Header>
      <Accordion.Content class="admin-accordion-content">
        <div class="admin-card-body">
          {#if legacyDirtyCount}
            <div class="admin-editor-section-actions admin-tariff-settings-save-row">
              <AdminBadge variant="warning">
                {at(
                  "settings_dirty_count",
                  { count: legacyDirtyCount },
                  `Изменений: ${legacyDirtyCount}`
                )}
              </AdminBadge>
              <AdminButton
                size="sm"
                variant="primary"
                onclick={saveTariffSettings}
                disabled={settingsSaving}
              >
                <Save size={13} />
                {settingsSaving
                  ? at("btn_saving", {}, "Сохранение...")
                  : at("btn_save", {}, "Сохранить")}
              </AdminButton>
            </div>
          {/if}
          <div class="admin-settings-warning" role="status">
            <TriangleAlert size={16} aria-hidden="true" />
            <div class="admin-settings-warning-copy">
              <strong>{at("settings_legacy_tariffs_warning_title", {}, "Legacy tariffs")}</strong>
              <p>
                {at(
                  "settings_legacy_tariffs_warning_body",
                  {},
                  "These settings are ignored when tariffs are configured in the dedicated Tariffs section."
                )}
              </p>
            </div>
          </div>

          <div class="admin-legacy-tariff-table">
            <div class="admin-legacy-tariff-row admin-legacy-tariff-head">
              <span>{at("tariffs_legacy_period", {}, "Period")}</span>
              <span>{at("tariffs_legacy_enabled", {}, "Enabled")}</span>
              <span>{at("payment_rub", {}, "RUB")}</span>
              <span>{at("payment_stars", {}, "Stars")}</span>
            </div>
            {#each LEGACY_PERIODS as [months, enabledKey, rubKey, starsKey]}
              <div class="admin-legacy-tariff-row">
                <strong>{months} {at("months_short", {}, "mo")}</strong>
                <div class="admin-setting-switch">
                  <Switch.Root
                    checked={boolValue(enabledKey)}
                    onCheckedChange={(checked) => setSetting(enabledKey, checked)}
                    class="admin-switch-root"
                  >
                    <Switch.Thumb class="admin-switch-thumb" />
                  </Switch.Root>
                </div>
                <input
                  class="input"
                  type="number"
                  min="0"
                  step="1"
                  value={valueForKey(rubKey)}
                  oninput={(event) => setSetting(rubKey, event.currentTarget.value)}
                />
                <input
                  class="input"
                  type="number"
                  min="0"
                  step="1"
                  value={valueForKey(starsKey)}
                  oninput={(event) => setSetting(starsKey, event.currentTarget.value)}
                />
              </div>
            {/each}
          </div>

          <div class="admin-form-row admin-form-row-2 admin-legacy-traffic-row">
            <label class="admin-field-label admin-field-label-compact">
              <span>{at("tariffs_legacy_traffic_packages", {}, "Traffic packages")}</span>
              <small>{at("tariffs_legacy_traffic_hint", {}, "Format: 10:199,50:799")}</small>
              <input
                class="input"
                type="text"
                value={valueForKey("TRAFFIC_PACKAGES")}
                oninput={(event) => setSetting("TRAFFIC_PACKAGES", event.currentTarget.value)}
              />
            </label>
            <label class="admin-field-label admin-field-label-compact">
              <span
                >{at("tariffs_legacy_stars_traffic_packages", {}, "Traffic packages, Stars")}</span
              >
              <small>{at("tariffs_legacy_traffic_hint", {}, "Format: 10:199,50:799")}</small>
              <input
                class="input"
                type="text"
                value={valueForKey("STARS_TRAFFIC_PACKAGES")}
                oninput={(event) => setSetting("STARS_TRAFFIC_PACKAGES", event.currentTarget.value)}
              />
            </label>
          </div>
        </div>
      </Accordion.Content>
    </Accordion.Item>
  </Accordion.Root>
{/if}
