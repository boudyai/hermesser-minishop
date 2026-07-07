<script lang="ts">
  import { getUsersStore } from "$lib/admin/context";
  import { onMount } from "svelte";
  import { trafficOfLabel } from "../../lib/admin/format.js";
  import { TableHandler } from "@vincjo/datatables";
  import UsersView from "./users/UsersView.svelte";
  import type { AdminUser } from "../../lib/admin/stores/usersStore";
  import type { AdminBadgeVariant } from "$components/patterns/admin/types";

  type TranslateFn = (key: string, params?: Record<string, unknown>, fallback?: string) => string;
  type SelectOption = { value: string; label: string };
  type SortColumn = {
    asc: string;
    desc: string;
    defaultDirection: "asc" | "desc";
  };
  type UserTableColumn = {
    key: string;
    label: string;
    sort?: SortColumn;
  };
  type ComponentCallback = () => void;
  type FilterKey = "usersFilter" | "usersPanelStatus" | "usersPremiumTraffic";
  type FilterPatch = Partial<Record<FilterKey, string>> & { usersPage?: number };
  type FilterChip = { key: FilterKey; label: string; value: string };
  type UsersSectionProps = {
    at?: TranslateFn;
    fmtDateShort?: (value: string | null | undefined) => string;
    fmtMoney?: (value: number, currency?: string | null) => string;
    hermesMode?: boolean;
    panelStatusBadge?: (user: AdminUser) => { label?: string; variant?: AdminBadgeVariant };
    resolvedAvatarUrl?: (user: AdminUser) => string;
    userDisplayName?: (user: AdminUser) => string;
    userInitials?: (user: AdminUser) => string;
    userSecondaryName?: (user: AdminUser) => string;
  };
  type TrafficBadge =
    | {
        state?: string;
        used_bytes?: number | string | null;
        limit_bytes?: number | string | null;
      }
    | null
    | undefined;
  type CornllmBalance =
    | {
        state?: string;
        max_budget?: number | string | null;
        spent?: number | string | null;
        remaining?: number | string | null;
        budget_duration?: string | null;
      }
    | null
    | undefined;
  type AdminUserWithCornllm = AdminUser & { cornllm?: CornllmBalance };

  let {
    at = (key) => key,
    fmtDateShort = (value) => String(value || ""),
    fmtMoney = (value) => String(value),
    hermesMode = false,
    panelStatusBadge = () => ({}),
    resolvedAvatarUrl = () => "",
    userDisplayName = () => "",
    userInitials = () => "",
    userSecondaryName = () => "",
  }: UsersSectionProps = $props();

  const usersStore = getUsersStore();
  const usersTable = new TableHandler<AdminUser>();
  const usersState = $derived(usersStore);
  const users = $derived(usersState.users);
  const usersTotal = $derived(usersState.usersTotal);
  const usersPage = $derived(usersState.usersPage);
  const usersQuery = $derived(usersState.usersQuery);
  const usersFilter = $derived(usersState.usersFilter);
  const usersPanelStatus = $derived(usersState.usersPanelStatus);
  const usersPremiumTraffic = $derived(usersState.usersPremiumTraffic);
  const usersSort = $derived(usersState.usersSort);
  const usersLoading = $derived(usersState.usersLoading);

  $effect(() => {
    usersTable.setRows(users);
  });

  const USERS_PAGE_SIZE = 25;
  let usersFilterSheetOpen = $state(false);
  const usersPageCount = $derived(
    Math.max(1, Math.ceil(Number(usersTotal || 0) / USERS_PAGE_SIZE))
  );

  const USERS_FILTER_OPTIONS = $derived([
    { value: "all", label: at("filter_all", {}, "Все") },
    { value: "active", label: at("filter_not_banned", {}, "Не забанены") },
    { value: "banned", label: at("filter_banned", {}, "Забанены") },
    { value: "tg_linked", label: at("filter_tg_linked", {}, "С Telegram") },
    { value: "no_tg", label: at("filter_no_tg", {}, "Без Telegram") },
    { value: "email_linked", label: at("filter_email_linked", {}, "С email") },
    { value: "no_email", label: at("filter_no_email", {}, "Без email") },
    { value: "panel_linked", label: at("filter_panel_linked", {}, "С панелью") },
  ] satisfies SelectOption[]);

  const SORT_COLUMNS = {
    user: { asc: "name_asc", desc: "name_desc", defaultDirection: "asc" },
    premium: { asc: "premium_ratio_asc", desc: "premium_ratio_desc", defaultDirection: "desc" },
    paymentsTotal: {
      asc: "payments_total_asc",
      desc: "payments_total_desc",
      defaultDirection: "desc",
    },
    paymentsCount: {
      asc: "payments_count_asc",
      desc: "payments_count_desc",
      defaultDirection: "desc",
    },
    invited: {
      asc: "invited_users_count_asc",
      desc: "invited_users_count_desc",
      defaultDirection: "desc",
    },
    subscriptionExpires: {
      asc: "subscription_expires_at_asc",
      desc: "subscription_expires_at_desc",
      defaultDirection: "asc",
    },
    registration: { asc: "registered_asc", desc: "registered_desc", defaultDirection: "desc" },
  } satisfies Record<string, SortColumn>;

  const USERS_PANEL_STATUS_OPTIONS = $derived([
    { value: "all", label: at("panel_status_all", {}, "Все статусы") },
    { value: "active", label: at("status_active", {}, "active") },
    { value: "expired", label: at("status_expired", {}, "expired") },
    { value: "limited", label: at("status_limited", {}, "limited") },
  ] satisfies SelectOption[]);

  const USERS_PREMIUM_TRAFFIC_OPTIONS = $derived([
    { value: "all", label: at("premium_traffic_filter_all", {}, "Все (премиум)") },
    { value: "none", label: at("premium_traffic_filter_none", {}, "Без лимита в тарифе") },
    {
      value: "unlimited",
      label: at("premium_traffic_filter_unlimited", {}, "Безлимит (оверрайд)"),
    },
    { value: "good", label: at("premium_traffic_filter_good", {}, "Премиум: норма") },
    { value: "warn", label: at("premium_traffic_filter_warn", {}, "Премиум: мало") },
    { value: "critical", label: at("premium_traffic_filter_critical", {}, "Премиум: исчерпан") },
  ] satisfies SelectOption[]);

  function optionLabel(options: SelectOption[], value: string): string {
    return options.find((item) => item.value === value)?.label || value;
  }

  function updateUsersFilterState(patch: FilterPatch): void {
    usersStore.updateState({ ...patch, usersPage: 0 });
    void usersStore.loadUsers();
  }

  const updateUsersFilter = ((value: string) =>
    updateUsersFilterState({ usersFilter: value })) as ComponentCallback;
  const updateUsersPanelStatus = ((value: string) =>
    updateUsersFilterState({ usersPanelStatus: value })) as ComponentCallback;
  const updateUsersPremiumTraffic = ((value: string) =>
    updateUsersFilterState({ usersPremiumTraffic: value })) as ComponentCallback;
  const updateToolbarUsersFilter = ((value: string) => {
    usersStore.updateState({ usersFilter: value, usersPage: 0 });
    void usersStore.loadUsers();
  }) as ComponentCallback;
  const updateToolbarPanelStatus = ((value: string) => {
    usersStore.updateState({ usersPanelStatus: value, usersPage: 0 });
    void usersStore.loadUsers();
  }) as ComponentCallback;
  const updateToolbarPremiumTraffic = ((value: string) => {
    usersStore.updateState({ usersPremiumTraffic: value, usersPage: 0 });
    void usersStore.loadUsers();
  }) as ComponentCallback;

  function resetUsersFilters(): void {
    updateUsersFilterState({
      usersFilter: "all",
      usersPanelStatus: "all",
      usersPremiumTraffic: "all",
    });
  }

  function clearUsersFilter(key: FilterKey): void {
    if (key === "usersFilter") updateUsersFilterState({ usersFilter: "all" });
    if (key === "usersPanelStatus") updateUsersFilterState({ usersPanelStatus: "all" });
    if (key === "usersPremiumTraffic") updateUsersFilterState({ usersPremiumTraffic: "all" });
  }

  function isFilterChip(value: FilterChip | false): value is FilterChip {
    return Boolean(value);
  }

  function premiumTrafficBadgeVariant(pt: TrafficBadge): AdminBadgeVariant {
    if (!pt || pt.state === "none") return "muted";
    if (pt.state === "unlimited" || pt.state === "good") return "success";
    if (pt.state === "warn") return "warning";
    return "danger";
  }

  function premiumTrafficBadgeText(pt: TrafficBadge): string {
    if (!pt || pt.state === "none") return "";
    if (pt.state === "unlimited") return trafficOfLabel(pt.used_bytes, 0);
    return trafficOfLabel(pt.used_bytes, pt.limit_bytes);
  }

  function cornllmBalance(user: AdminUser): CornllmBalance {
    return (user as AdminUserWithCornllm).cornllm;
  }

  function numberOrNull(value: unknown): number | null {
    const num = Number(value);
    return Number.isFinite(num) ? num : null;
  }

  function rubFromUsd(value: unknown): string {
    const usd = numberOrNull(value);
    if (usd === null) return "—";
    const rub = usd * 100;
    return `${rub.toLocaleString("ru-RU", { maximumFractionDigits: 2 })} ₽`;
  }

  function cornllmBadgeVariant(balance: CornllmBalance): AdminBadgeVariant {
    const state = String(balance?.state || "").toLowerCase();
    if (!balance || state === "none") return "muted";
    if (state === "unreachable") return "warning";
    const remaining = numberOrNull(balance.remaining);
    if (remaining !== null && remaining <= 0) return "danger";
    if (remaining !== null && remaining < 1) return "warning";
    return "success";
  }

  function cornllmBadgeText(balance: CornllmBalance): string {
    const state = String(balance?.state || "").toLowerCase();
    if (!balance || state === "none") return at("cornllm_balance_no_key", {}, "нет ключа");
    if (state === "unreachable") return at("cornllm_balance_unreachable", {}, "н/д");
    const remaining = rubFromUsd(balance.remaining);
    const maxBudget = rubFromUsd(balance.max_budget);
    return `${remaining} / ${maxBudget}`;
  }

  function cornllmBadgeTitle(balance: CornllmBalance): string {
    const spent = rubFromUsd(balance?.spent);
    return `${at("cornllm_balance_spent", {}, "потрачено")}: ${spent}`;
  }

  function userTableColumns(): UserTableColumn[] {
    return [
      { key: "user", label: at("user", {}, "Пользователь"), sort: SORT_COLUMNS.user },
      {
        key: "premium",
        label: hermesMode
          ? at("cornllm_balance", {}, "CornLLM")
          : at("premium_traffic_filter_label", {}, "Премиум трафик"),
        sort: hermesMode ? undefined : SORT_COLUMNS.premium,
      },
      {
        key: "paymentsTotal",
        label: at("users_col_payments_total", {}, "Сумма платежей"),
        sort: SORT_COLUMNS.paymentsTotal,
      },
      {
        key: "paymentsCount",
        label: at("users_col_payments_count", {}, "Платежи"),
        sort: SORT_COLUMNS.paymentsCount,
      },
      {
        key: "invited",
        label: at("users_col_invited", {}, "Приглашенные"),
        sort: SORT_COLUMNS.invited,
      },
      { key: "status", label: at("status", {}, "Статус") },
      {
        key: "subscriptionExpires",
        label: at("users_col_subscription_expires", {}, "Истекает"),
        sort: SORT_COLUMNS.subscriptionExpires,
      },
      {
        key: "registration",
        label: at("users_col_registration", {}, "Регистрация"),
        sort: SORT_COLUMNS.registration,
      },
    ];
  }

  function sortState(column: SortColumn | undefined): "none" | "ascending" | "descending" {
    if (!column) return "none";
    if (usersSort === column.asc) return "ascending";
    if (usersSort === column.desc) return "descending";
    return "none";
  }

  function nextSortValue(column: SortColumn): string {
    const state = sortState(column);
    const defaultValue = column[column.defaultDirection] || column.asc;
    if (state === "none") return defaultValue;
    if (usersSort === defaultValue) {
      return column.defaultDirection === "asc" ? column.desc : column.asc;
    }
    return "";
  }

  function toggleUsersSort(column: SortColumn): void {
    usersStore.updateState({ usersSort: nextSortValue(column), usersPage: 0 });
    void usersStore.loadUsers();
  }

  function toggleUsersSortForColumn(column: UserTableColumn): void {
    if (column.sort) toggleUsersSort(column.sort);
  }

  function sortTitle(column: SortColumn): string {
    const state = sortState(column);
    if (state === "ascending") return at("sort_ascending", {}, "По возрастанию");
    if (state === "descending") return at("sort_descending", {}, "По убыванию");
    return at("sort_off", {}, "Без сортировки");
  }

  function rowPaymentsTotal(user: AdminUser): string {
    return fmtMoney(user?.payments_total_amount ?? 0, user?.payments_currency || "RUB");
  }

  function handleUsersSearchInput(event: Event): void {
    const input = event.currentTarget as HTMLInputElement | null;
    usersStore.updateState({ usersQuery: input?.value || "" });
  }

  function handleUsersSearchKeydown(event: KeyboardEvent): void {
    if (event.key !== "Enter") return;
    usersStore.updateState({ usersPage: 0 });
    void usersStore.loadUsers();
  }

  const activeUserFilterChips = $derived(
    (
      [
        usersFilter !== "all" && {
          key: "usersFilter",
          label: at("filter", {}, "Фильтр"),
          value: optionLabel(USERS_FILTER_OPTIONS, usersFilter),
        },
        usersPanelStatus !== "all" && {
          key: "usersPanelStatus",
          label: at("panel_status", {}, "Статус панели"),
          value: optionLabel(USERS_PANEL_STATUS_OPTIONS, usersPanelStatus),
        },
        usersPremiumTraffic !== "all" && {
          key: "usersPremiumTraffic",
          label: at("premium_traffic_filter_label", {}, "Премиум трафик"),
          value: optionLabel(USERS_PREMIUM_TRAFFIC_OPTIONS, usersPremiumTraffic),
        },
      ] satisfies (FilterChip | false)[]
    ).filter(isFilterChip)
  );
  const activeUsersFilterCount = $derived(activeUserFilterChips.length);
  const userTableHeaders = $derived(userTableColumns().map((column) => column.label));

  onMount(() => {
    usersStore.loadUsers();
  });
</script>

<UsersView
  {at}
  {usersStore}
  {usersTable}
  bind:usersFilterSheetOpen
  {usersFilter}
  {usersPanelStatus}
  {usersPremiumTraffic}
  {usersQuery}
  {usersTotal}
  {usersPage}
  {usersPageCount}
  {usersLoading}
  {USERS_PAGE_SIZE}
  {USERS_FILTER_OPTIONS}
  {USERS_PANEL_STATUS_OPTIONS}
  {USERS_PREMIUM_TRAFFIC_OPTIONS}
  {activeUsersFilterCount}
  {activeUserFilterChips}
  {hermesMode}
  {userTableHeaders}
  {updateUsersFilter}
  {updateUsersPanelStatus}
  {updateUsersPremiumTraffic}
  {updateToolbarUsersFilter}
  {updateToolbarPanelStatus}
  {updateToolbarPremiumTraffic}
  {resetUsersFilters}
  {clearUsersFilter}
  {handleUsersSearchInput}
  {handleUsersSearchKeydown}
  {userTableColumns}
  {sortState}
  {sortTitle}
  {toggleUsersSortForColumn}
  {resolvedAvatarUrl}
  {panelStatusBadge}
  {userInitials}
  {userDisplayName}
  {userSecondaryName}
  {cornllmBalance}
  {cornllmBadgeVariant}
  {cornllmBadgeText}
  {cornllmBadgeTitle}
  {premiumTrafficBadgeVariant}
  {premiumTrafficBadgeText}
  {rowPaymentsTotal}
  {fmtDateShort}
/>
