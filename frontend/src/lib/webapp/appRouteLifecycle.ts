import { isPasswordLoginPath } from "./passwordLoginRoute.js";
import { activeTabForWebappSection, resolveAvailableWebappSection } from "./sectionAvailability.js";
import { adminSectionFromPath, normalizeSection, sectionFromPath } from "./routes.js";

// ponytail: public install-mode was retired on 2026-07-04 alongside the
// /s/{token} share-link flow. Old messages may still contain the URL
// but the backend now 302s them to /install, so the frontend just
// needs to route to the install section as usual.
export type PopstateMode = "app" | "login" | string;

export type PopstateRouteDecision =
  | { kind: "boot" }
  | { kind: "login"; passwordLoginEnabled: boolean }
  | { kind: "admin"; adminSection: string; activeTab: "settings"; section: "admin" }
  | {
      kind: "section";
      activeTab: string;
      loadDevices: boolean;
      loadInstallGuides: boolean;
      loadSupport: boolean;
      section: string;
    }
  | { kind: "ignore" };

export type PopstateRouteInput = {
  canUseInstallGuides?: boolean;
  devicesEnabled?: boolean;
  fallbackAdminSection: string;
  isAdmin?: boolean;
  isDocsDemo?: boolean;
  mode: PopstateMode;
  pathname: string;
  routePrefix?: string;
  screenQuery?: string | null;
  supportEnabled?: boolean;
};

export function resolvePopstateRoute({
  canUseInstallGuides = false,
  devicesEnabled = false,
  fallbackAdminSection,
  isAdmin = false,
  isDocsDemo = false,
  mode,
  pathname,
  routePrefix = "",
  screenQuery = null,
  supportEnabled = true,
}: PopstateRouteInput): PopstateRouteDecision {
  const routeSection =
    isDocsDemo && screenQuery
      ? normalizeSection(screenQuery)
      : sectionFromPath(pathname, routePrefix);
  if (mode === "login") {
    return {
      kind: "login",
      passwordLoginEnabled: isPasswordLoginPath(pathname),
    };
  }
  if (mode !== "app") return { kind: "ignore" };
  if (routeSection === "admin" && isAdmin) {
    return {
      activeTab: "settings",
      adminSection: isDocsDemo ? fallbackAdminSection : adminSectionFromPath(pathname, routePrefix),
      kind: "admin",
      section: "admin",
    };
  }

  const section = resolveAvailableWebappSection({
    devicesEnabled,
    installGuidesAvailable: canUseInstallGuides,
    isAdmin,
    section: routeSection,
    supportEnabled,
  });
  return {
    activeTab: activeTabForWebappSection(section),
    kind: "section",
    loadDevices: section === "devices",
    loadInstallGuides: section === "install",
    loadSupport: section === "support",
    section,
  };
}
