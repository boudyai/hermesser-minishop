import { resolvePopstateRoute, type PopstateRouteDecision } from "./appRouteLifecycle.js";
import { sectionFromPath } from "./routes.js";
import { shellState } from "./shellState.svelte";

type MaybePromise<T = void> = T | Promise<T>;

type AdminRuntime = {
  cancelAdminAssetsPrefetch: () => void;
  ensureAdminBundle: () => Promise<unknown>;
  ensureI18nScope: (scope: string) => Promise<unknown>;
};

type PopstateLifecycleDeps = {
  adminRuntime: AdminRuntime;
  boot: () => MaybePromise;
  canUseInstallGuides: () => boolean;
  currentSearchParams: () => URLSearchParams;
  getDevicesEnabled: () => boolean;
  getFallbackAdminSection: () => string;
  getIsAdmin: () => boolean;
  getSupportEnabled: () => boolean;
  getWindowPathname?: () => string;
  isDocsDemo: boolean;
  loadDevices: () => void;
  loadInstallGuides: () => void;
  loadSupport: () => void;
  routePathnameFromLocation: () => string;
  routePrefix: string;
  setPasswordLoginMode: (enabled: boolean, replace?: boolean) => void;
  showAdminUnavailable: () => void;
  startSupportPolling: () => void;
  syncAppSectionPath: (section: string, replace?: boolean) => void;
};

export function createPopstateLifecycle({
  adminRuntime,
  boot,
  canUseInstallGuides,
  currentSearchParams,
  getDevicesEnabled,
  getFallbackAdminSection,
  getIsAdmin,
  getSupportEnabled,
  getWindowPathname = () => (typeof window === "undefined" ? "" : window.location.pathname),
  isDocsDemo,
  loadDevices,
  loadInstallGuides,
  loadSupport,
  routePathnameFromLocation,
  routePrefix,
  setPasswordLoginMode,
  showAdminUnavailable,
  startSupportPolling,
  syncAppSectionPath,
}: PopstateLifecycleDeps) {
  function handleAdminDecision(decision: Extract<PopstateRouteDecision, { kind: "admin" }>): void {
    shellState.adminActiveSection = decision.adminSection;
    adminRuntime.cancelAdminAssetsPrefetch();
    shellState.activeTab = decision.activeTab;
    shellState.screen = decision.section;
    const pathAtStart = getWindowPathname();
    void Promise.all([
      adminRuntime.ensureI18nScope("admin"),
      adminRuntime.ensureAdminBundle(),
    ]).catch(() => {
      if (sectionFromPath(routePathnameFromLocation(), routePrefix) !== "admin") return;
      if (getWindowPathname() !== pathAtStart) return;
      if (shellState.screen === "admin") {
        shellState.activeTab = "settings";
        shellState.screen = "settings";
        syncAppSectionPath("settings", true);
      }
      showAdminUnavailable();
    });
  }

  function handleSectionDecision(
    decision: Extract<PopstateRouteDecision, { kind: "section" }>
  ): void {
    shellState.activeTab = decision.activeTab;
    shellState.screen = decision.section;
    if (decision.loadDevices) loadDevices();
    if (decision.loadSupport) {
      loadSupport();
      startSupportPolling();
    }
    if (decision.loadInstallGuides) loadInstallGuides();
  }

  function handlePopstate(): PopstateRouteDecision {
    const currentQuery = currentSearchParams();
    const decision = resolvePopstateRoute({
      canUseInstallGuides: canUseInstallGuides(),
      devicesEnabled: getDevicesEnabled(),
      fallbackAdminSection: getFallbackAdminSection(),
      isAdmin: getIsAdmin(),
      isDocsDemo,
      mode: shellState.mode,
      pathname: routePathnameFromLocation(),
      routePrefix,
      screenQuery: currentQuery.get("screen"),
      supportEnabled: getSupportEnabled(),
    });

    if (decision.kind === "boot") {
      void boot();
      return decision;
    }
    if (decision.kind === "login") {
      setPasswordLoginMode(decision.passwordLoginEnabled, true);
      shellState.screen = "login";
      return decision;
    }
    if (decision.kind === "admin") {
      handleAdminDecision(decision);
      return decision;
    }
    if (decision.kind === "section") {
      handleSectionDecision(decision);
    }
    return decision;
  }

  return {
    handlePopstate,
  };
}
