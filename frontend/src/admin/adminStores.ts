import { QueryClient } from "@tanstack/svelte-query";
import { createAdsStore } from "../lib/admin/stores/adsStore.js";
import type { AdsStore } from "../lib/admin/stores/adsStore";
import { createBackupsStore } from "../lib/admin/stores/backupsStore.js";
import type { BackupsStore } from "../lib/admin/stores/backupsStore";
import { createBroadcastStore } from "../lib/admin/stores/broadcastStore.js";
import type { BroadcastStore } from "../lib/admin/stores/broadcastStore";
import { createHealthStore } from "../lib/admin/stores/healthStore.js";
import type { HealthApi, HealthStore } from "../lib/admin/stores/healthStore";
import { createLogsStore } from "../lib/admin/stores/logsStore.js";
import type { LogsStore } from "../lib/admin/stores/logsStore";
import { createPaymentsStore } from "../lib/admin/stores/paymentsStore.js";
import type { PaymentsStore } from "../lib/admin/stores/paymentsStore";
import { createPromosStore } from "../lib/admin/stores/promosStore.js";
import type { PromosStore } from "../lib/admin/stores/promosStore";
import { createSettingsStore } from "../lib/admin/stores/settingsStore.js";
import type { SettingsStore } from "../lib/admin/stores/settingsStore";
import { createStatsStore } from "../lib/admin/stores/statsStore.js";
import type { StatsStore } from "../lib/admin/stores/statsStore";
import { createAdminSupportStore } from "../lib/admin/stores/supportStore.js";
import type { AdminSupportStore } from "../lib/admin/stores/supportStore";
import { createTariffsStore } from "../lib/admin/stores/tariffsStore.js";
import type { TariffsStore } from "../lib/admin/stores/tariffsStore";
import { createThemesStore } from "../lib/admin/stores/themesStore.js";
import type { ThemesStore } from "../lib/admin/stores/themesStore";
import { createTranslationsStore } from "../lib/admin/stores/translationsStore.js";
import type { TranslationsStore } from "../lib/admin/stores/translationsStore";
import { createUsersStore } from "../lib/admin/stores/usersStore.js";
import type { UsersStore } from "../lib/admin/stores/usersStore";
import {
  setAdsStore,
  setAdminSupportStore,
  setBackupsStore,
  setBroadcastStore,
  setHealthStore,
  setLogsStore,
  setPaymentsStore,
  setPromosStore,
  setSettingsStore,
  setStatsStore,
  setTariffsStore,
  setThemesStore,
  setTranslationsStore,
  setUsersStore,
} from "../lib/admin/context";
import type { TariffsCatalog } from "../lib/admin/stores/tariffsStore";
import type { ApiClient } from "../lib/webapp/publicApi";

export type AdminApi = ApiClient["api"];
type TranslateFn = (key: string, params?: Record<string, unknown>, fallback?: string) => string;

type AdminStores = {
  adminQueryClient: QueryClient;
  adsStore: AdsStore;
  backupsStore: BackupsStore;
  broadcastStore: BroadcastStore;
  healthStore: HealthStore;
  logsStore: LogsStore;
  paymentsStore: PaymentsStore;
  promosStore: PromosStore;
  settingsStore: SettingsStore;
  statsStore: StatsStore;
  supportStore: AdminSupportStore;
  tariffsStore: TariffsStore;
  themesStore: ThemesStore;
  translationsStore: TranslationsStore;
  usersStore: UsersStore;
};

type AdminStoresOptions = {
  api: AdminApi;
  at: TranslateFn;
  onToast: (message: string) => void;
  onTariffsSaved: (catalog: TariffsCatalog) => void | Promise<void>;
  onThemesSaved: () => void | Promise<void>;
  routePrefix: string;
};

export function createAdminStores({
  api,
  at,
  onToast,
  onTariffsSaved,
  onThemesSaved,
  routePrefix,
}: AdminStoresOptions): AdminStores {
  const adminQueryClient = new QueryClient({
    defaultOptions: {
      queries: {
        gcTime: 10 * 60 * 1000,
        retry: false,
        staleTime: 60 * 1000,
      },
    },
  });
  const healthApi = api as HealthApi;
  const settingsStore: SettingsStore = createSettingsStore({
    api: api as Parameters<typeof createSettingsStore>[0]["api"],
    onToast,
    at,
  });
  const adsStore: AdsStore = createAdsStore({
    api: api as Parameters<typeof createAdsStore>[0]["api"],
    onToast,
    at,
  });
  const backupsStore: BackupsStore = createBackupsStore({
    api: api as Parameters<typeof createBackupsStore>[0]["api"],
    onToast,
    at,
  });
  const broadcastStore: BroadcastStore = createBroadcastStore({
    api: api as Parameters<typeof createBroadcastStore>[0]["api"],
    onToast,
    at,
  });
  const healthStore: HealthStore = createHealthStore({ api: healthApi, at });
  const logsStore: LogsStore = createLogsStore({
    api: api as Parameters<typeof createLogsStore>[0]["api"],
    onToast,
    at,
    queryClient: adminQueryClient,
  });
  const paymentsStore: PaymentsStore = createPaymentsStore({
    api: api as Parameters<typeof createPaymentsStore>[0]["api"],
    onToast,
    at,
    routePrefix,
    queryClient: adminQueryClient,
  });
  const promosStore: PromosStore = createPromosStore({
    api: api as Parameters<typeof createPromosStore>[0]["api"],
    onToast,
    at,
    queryClient: adminQueryClient,
  });
  const statsStore: StatsStore = createStatsStore({
    api: api as Parameters<typeof createStatsStore>[0]["api"],
    onToast,
    at,
    queryClient: adminQueryClient,
  });
  const supportStore: AdminSupportStore = createAdminSupportStore({
    api: api as Parameters<typeof createAdminSupportStore>[0]["api"],
    onToast,
    at,
    routePrefix,
  });
  const tariffsStore: TariffsStore = createTariffsStore({
    api: api as Parameters<typeof createTariffsStore>[0]["api"],
    onTariffsSaved,
    flash: onToast,
    at,
  });
  const themesStore: ThemesStore = createThemesStore({
    api: api as Parameters<typeof createThemesStore>[0]["api"],
    onThemesSaved,
    flash: onToast,
    at,
  });
  const translationsStore: TranslationsStore = createTranslationsStore({
    api: api as Parameters<typeof createTranslationsStore>[0]["api"],
    onToast,
    at,
  });
  const usersStore: UsersStore = createUsersStore({
    api: api as Parameters<typeof createUsersStore>[0]["api"],
    onToast,
    at,
    routePrefix,
    queryClient: adminQueryClient,
  });

  setPromosStore(promosStore);
  setAdsStore(adsStore);
  setHealthStore(healthStore);
  setBackupsStore(backupsStore);
  setBroadcastStore(broadcastStore);
  setLogsStore(logsStore);
  setPaymentsStore(paymentsStore);
  setStatsStore(statsStore);
  setAdminSupportStore(supportStore);
  setSettingsStore(settingsStore);
  setUsersStore(usersStore);
  setTariffsStore(tariffsStore);
  setThemesStore(themesStore);
  setTranslationsStore(translationsStore);

  return {
    adminQueryClient,
    adsStore,
    backupsStore,
    broadcastStore,
    healthStore,
    logsStore,
    paymentsStore,
    promosStore,
    settingsStore,
    statsStore,
    supportStore,
    tariffsStore,
    themesStore,
    translationsStore,
    usersStore,
  };
}
