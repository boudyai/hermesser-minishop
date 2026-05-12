<script>
  import { Label } from "$components/ui/primitives.js";
  import {
    AdminBadge,
    AdminButton,
    AdminEmptyState,
    AdminPagination,
    AdminSelect,
    AdminTable,
    AdminTableSkeleton,
  } from "$components/patterns/admin/index.js";
  import { getContext, onMount } from "svelte";
  import { trafficOfLabel } from "../../lib/admin/format.js";

  export let at = (key) => key;
  export let fmtDateShort = (value) => value;
  export let panelStatusBadge = () => ({});
  export let resolvedAvatarUrl = () => "";
  export let userDisplayName = () => "";
  export let userInitials = () => "";
  export let userSecondaryName = () => "";

  const usersStore = getContext("usersStore");

  $: ({
    users,
    usersTotal,
    usersPage,
    usersQuery,
    usersFilter,
    usersPanelStatus,
    usersPremiumTraffic,
    usersSort,
    usersLoading,
  } = $usersStore);

  const USERS_PAGE_SIZE = 25;
  $: usersHasMore = users.length === USERS_PAGE_SIZE;

  const USERS_FILTER_OPTIONS = [
    { value: "all", label: at("filter_all", {}, "Все") },
    { value: "active", label: at("filter_not_banned", {}, "Не забанены") },
    { value: "banned", label: at("filter_banned", {}, "Забанены") },
    { value: "tg_linked", label: at("filter_tg_linked", {}, "С Telegram") },
    { value: "no_tg", label: at("filter_no_tg", {}, "Без Telegram") },
    { value: "email_linked", label: at("filter_email_linked", {}, "С email") },
    { value: "no_email", label: at("filter_no_email", {}, "Без email") },
    { value: "panel_linked", label: at("filter_panel_linked", {}, "С панелью") },
  ];

  const USERS_SORT_OPTIONS = [
    { value: "registered_desc", label: at("sort_registered_desc", {}, "Сначала новые") },
    { value: "registered_asc", label: at("sort_registered_asc", {}, "Сначала старые") },
    { value: "name_asc", label: at("sort_name_asc", {}, "Имя ↑") },
    { value: "name_desc", label: at("sort_name_desc", {}, "Имя ↓") },
    { value: "id_asc", label: at("sort_id_asc", {}, "ID ↑") },
    { value: "id_desc", label: at("sort_id_desc", {}, "ID ↓") },
    { value: "premium_ratio_asc", label: at("sort_premium_ratio_asc", {}, "Премиум % ↑") },
    { value: "premium_ratio_desc", label: at("sort_premium_ratio_desc", {}, "Премиум % ↓") },
  ];

  const USERS_PANEL_STATUS_OPTIONS = [
    { value: "all", label: at("panel_status_all", {}, "Все статусы") },
    { value: "active", label: at("status_active", {}, "active") },
    { value: "expired", label: at("status_expired", {}, "expired") },
    { value: "limited", label: at("status_limited", {}, "limited") },
  ];

  const USERS_PREMIUM_TRAFFIC_OPTIONS = [
    { value: "all", label: at("premium_traffic_filter_all", {}, "Все (премиум)") },
    { value: "none", label: at("premium_traffic_filter_none", {}, "Без лимита в тарифе") },
    { value: "unlimited", label: at("premium_traffic_filter_unlimited", {}, "Безлимит (оверрайд)") },
    { value: "good", label: at("premium_traffic_filter_good", {}, "Премиум: норма") },
    { value: "warn", label: at("premium_traffic_filter_warn", {}, "Премиум: мало") },
    { value: "critical", label: at("premium_traffic_filter_critical", {}, "Премиум: исчерпан") },
  ];

  /** @param {Record<string, unknown> | null | undefined} pt */
  function premiumTrafficBadgeVariant(pt) {
    if (!pt || pt.state === "none") return "muted";
    if (pt.state === "unlimited" || pt.state === "good") return "success";
    if (pt.state === "warn") return "warning";
    return "danger";
  }

  /** @param {Record<string, unknown> | null | undefined} pt */
  function premiumTrafficBadgeText(pt) {
    if (!pt || pt.state === "none") return "";
    if (pt.state === "unlimited") return trafficOfLabel(pt.used_bytes, 0);
    return trafficOfLabel(pt.used_bytes, pt.limit_bytes);
  }

  $: userTableHeaders = [
    at("user", {}, "Пользователь"),
    at("premium_traffic_filter_label", {}, "Премиум трафик"),
    at("status", {}, "Статус"),
    at("users_col_registration", {}, "Регистрация"),
  ];

  onMount(() => {
    usersStore.loadUsers();
  });
</script>

<div class="admin-toolbar admin-toolbar-users">
  <div class="admin-toolbar-search">
    <input
      type="search"
      class="input"
      placeholder={at("users_search_placeholder", {}, "ID, @username или email")}
      value={usersQuery}
      on:input={(e) => usersStore.updateState({ usersQuery: e.target.value })}
      on:keydown={(e) => e.key === "Enter" && (usersStore.updateState({ usersPage: 0 }), usersStore.loadUsers())}
    />
    <AdminButton variant="primary" onclick={() => { usersStore.updateState({ usersPage: 0 }); usersStore.loadUsers(); }}>{at("find", {}, "Найти")}</AdminButton>
  </div>

  <div class="admin-toolbar-controls">
    <Label.Root class="admin-toolbar-field">
      <span class="admin-toolbar-field-label">{at("filter", {}, "Фильтр")}</span>
      <AdminSelect
        value={usersFilter}
        items={USERS_FILTER_OPTIONS}
        class="admin-toolbar-select"
        ariaLabel={at("filter", {}, "Фильтр")}
        onValueChange={(value) => { usersStore.updateState({ usersFilter: value, usersPage: 0 }); usersStore.loadUsers(); }}
      />
    </Label.Root>

    <Label.Root class="admin-toolbar-field">
      <span class="admin-toolbar-field-label">{at("panel_status", {}, "Статус панели")}</span>
      <AdminSelect
        value={usersPanelStatus}
        items={USERS_PANEL_STATUS_OPTIONS}
        class="admin-toolbar-select"
        ariaLabel={at("panel_status", {}, "Статус панели")}
        onValueChange={(value) => { usersStore.updateState({ usersPanelStatus: value, usersPage: 0 }); usersStore.loadUsers(); }}
      />
    </Label.Root>

    <Label.Root class="admin-toolbar-field">
      <span class="admin-toolbar-field-label">{at("premium_traffic_filter_label", {}, "Премиум трафик")}</span>
      <AdminSelect
        value={usersPremiumTraffic}
        items={USERS_PREMIUM_TRAFFIC_OPTIONS}
        class="admin-toolbar-select"
        ariaLabel={at("premium_traffic_filter_label", {}, "Премиум трафик")}
        onValueChange={(value) => { usersStore.updateState({ usersPremiumTraffic: value, usersPage: 0 }); usersStore.loadUsers(); }}
      />
    </Label.Root>

    <Label.Root class="admin-toolbar-field">
      <span class="admin-toolbar-field-label">{at("sort", {}, "Сортировка")}</span>
      <AdminSelect
        value={usersSort}
        items={USERS_SORT_OPTIONS}
        class="admin-toolbar-select"
        ariaLabel={at("sort", {}, "Сортировка")}
        onValueChange={(value) => { usersStore.updateState({ usersSort: value, usersPage: 0 }); usersStore.loadUsers(); }}
      />
    </Label.Root>

    <div class="admin-toolbar-summary">
      <span class="admin-toolbar-field-label">{at("total", {}, "Всего")}</span>
      <strong>{usersTotal}</strong>
    </div>
  </div>
</div>

<div class="admin-table-wrap admin-users-table-wrap">
  {#if usersLoading}
    <AdminTableSkeleton
      headers={userTableHeaders}
      rows={USERS_PAGE_SIZE}
      widths={["minmax(220px, 42%)", "minmax(140px, 28%)", "108px", "112px"]}
    />
  {:else if !users.length}
    <AdminEmptyState tone="card"><span class="admin-muted">{at("users_empty", {}, "Никого не найдено")}</span></AdminEmptyState>
  {:else}
    <AdminTable class="admin-users-table">
      <thead>
        <tr>
          <th>{at("user", {}, "Пользователь")}</th>
          <th>{at("premium_traffic_filter_label", {}, "Премиум трафик")}</th>
          <th>{at("status", {}, "Статус")}</th>
          <th>{at("users_col_registration", {}, "Регистрация")}</th>
        </tr>
      </thead>
      <tbody>
        {#each users as user}
          {@const avatar = resolvedAvatarUrl(user)}
          {@const badge = panelStatusBadge(user)}
          <tr
            class="is-clickable"
            role="button"
            tabindex="0"
            data-user-id={user.user_id}
            on:click={() => usersStore.openUser(user)}
            on:keydown={(e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                usersStore.openUser(user);
              }
            }}
          >
            <td class="admin-users-cell-user" data-label={at("user", {}, "Пользователь")}>
              <div class="admin-users-cell-user-inner">
                <span class="admin-avatar admin-avatar-sm">
                  {#if avatar}
                    <img src={avatar} alt="" loading="lazy" referrerpolicy="no-referrer" />
                  {:else}
                    <span>{userInitials(user)}</span>
                  {/if}
                </span>
                <div class="admin-users-cell-user-text">
                  <span class="admin-users-cell-name">{userDisplayName(user)}</span>
                  <span class="admin-users-cell-secondary">{userSecondaryName(user)}</span>
                  <span class="admin-users-cell-id">#{user.user_id}</span>
                </div>
              </div>
            </td>
            <td class="admin-users-cell-premium" data-label={at("premium_traffic_filter_label", {}, "Премиум трафик")}>
              {#if user.premium_traffic && user.premium_traffic.state !== "none"}
                <AdminBadge variant={premiumTrafficBadgeVariant(user.premium_traffic)} class="admin-user-premium-badge">
                  {premiumTrafficBadgeText(user.premium_traffic)}
                </AdminBadge>
              {:else}
                <span class="admin-user-premium-placeholder">{at("premium_traffic_na", {}, "—")}</span>
              {/if}
            </td>
            <td data-label={at("status", {}, "Статус")}>
              <AdminBadge variant={badge.variant}>{badge.label}</AdminBadge>
            </td>
            <td class="admin-users-cell-date admin-cell-mono" data-label={at("users_col_registration", {}, "Регистрация")}>
              {fmtDateShort(user.registration_date)}
            </td>
          </tr>
        {/each}
      </tbody>
    </AdminTable>
  {/if}
</div>

<AdminPagination
  meta={`${at("page", {}, "Страница")} ${usersPage + 1}`}
  prevLabel={at("back", {}, "Назад")}
  nextLabel={at("next", {}, "Далее")}
  prevDisabled={usersPage === 0}
  nextDisabled={!usersHasMore}
  onPrev={() => { usersStore.updateState({ usersPage: Math.max(0, usersPage - 1) }); usersStore.loadUsers(); }}
  onNext={() => { usersStore.updateState({ usersPage: usersPage + 1 }); usersStore.loadUsers(); }}
/>

<style>
  .admin-users-cell-user-inner {
    display: flex;
    align-items: center;
    gap: 10px;
    min-width: 0;
  }

  .admin-users-cell-user-text {
    display: grid;
    gap: 2px;
    min-width: 0;
    text-align: left;
  }

  .admin-users-cell-name {
    font-weight: 650;
    font-size: 13px;
    line-height: 1.25;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .admin-users-cell-secondary {
    font-size: 11px;
    color: var(--admin-dim);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .admin-users-cell-id {
    font-family: var(--font-mono);
    font-size: 11px;
    color: var(--admin-muted);
  }

  .admin-users-cell-premium {
    white-space: nowrap;
  }

  .admin-users-cell-premium :global(.admin-user-premium-badge) {
    max-width: 220px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    font-size: 11px;
    font-variant-numeric: tabular-nums;
  }

  .admin-user-premium-placeholder {
    color: var(--admin-dim);
    font-size: 12px;
    font-variant-numeric: tabular-nums;
  }

  .admin-users-cell-date {
    white-space: nowrap;
    font-size: 12px;
    color: var(--admin-muted);
  }

  .admin-users-table-wrap :global(.admin-users-table tbody tr.is-clickable:focus-visible) {
    outline: 2px solid var(--admin-ring);
    outline-offset: -2px;
  }
</style>
