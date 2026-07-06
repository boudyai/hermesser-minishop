// Lifecycle state derivation for the tenant onboarding / status card.
//
// Lives outside the Svelte component so the state-machine rules can be
// unit-tested with vitest in milliseconds, without spinning up jsdom or
// a component harness. The Svelte component imports ``deriveLifecycleView``
// and reads the resulting flags / display strings.
//
// One helper per observable state. Adding a new card state means adding
// a flag here + a one-line case in the Svelte template, and the rules
// stay testable in isolation.

export type LifecycleState =
  "hidden" | "needs_token" | "provisioning" | "error" | "grace_period" | "suspended" | "deleting";

export interface LifecycleInput {
  hermesMode: boolean;
  hasBotToken: boolean;
  active: boolean;
  tenantStatus: string | null;
}

export interface LifecycleView {
  state: LifecycleState;
  showWizard: boolean;
  showProvisioning: boolean;
  showError: boolean;
  showGracePeriod: boolean;
  showSuspended: boolean;
  showDeleting: boolean;
  showNeedsToken: boolean;
}

// Statuses where the tenant is still being built — show a "setting up"
// card. Matches the four ``provisioning_*`` enum values in
// ``provisioning-core.app.db.models.TenantStatus`` plus the pre-build
// states (created / awaiting_payment / paid).
const PROVISIONING_STATUSES = new Set<string>([
  "created",
  "awaiting_payment",
  "paid",
  "provisioning_litellm_key",
  "provisioning_vm",
]);

export function deriveLifecycleView(input: LifecycleInput): LifecycleView {
  const { hermesMode, hasBotToken, active, tenantStatus } = input;

  // Out-of-scope: not in hermes mode, or the subscription is already
  // active. BotStatusCard takes over the active case.
  if (!hermesMode || active) {
    return emptyView("hidden");
  }

  // In-scope but no token yet — the 3-step @BotFather guide.
  if (!hasBotToken) {
    return { ...emptyView("needs_token"), showWizard: true, showNeedsToken: true };
  }

  // The user has a token but the tenant isn't active yet — map the
  // provisioning-core status to the right UX state.
  const status = String(tenantStatus || "").trim();

  if (PROVISIONING_STATUSES.has(status)) {
    return { ...emptyView("provisioning"), showWizard: true, showProvisioning: true };
  }
  if (status === "error") {
    return { ...emptyView("error"), showWizard: true, showError: true };
  }
  if (status === "payment_expiring") {
    return { ...emptyView("grace_period"), showWizard: true, showGracePeriod: true };
  }
  if (status === "suspended") {
    return { ...emptyView("suspended"), showWizard: true, showSuspended: true };
  }
  if (status === "deleting") {
    return { ...emptyView("deleting"), showWizard: true, showDeleting: true };
  }

  // Token is already saved, but there is no reliable tenant status yet
  // (e.g. trial not activated, core unreachable, or an archived/deleted tenant).
  // Hide this card rather than asking the user to paste the same token again.
  return emptyView("hidden");
}

function emptyView(state: LifecycleState): LifecycleView {
  return {
    state,
    showWizard: false,
    showProvisioning: false,
    showError: false,
    showGracePeriod: false,
    showSuspended: false,
    showDeleting: false,
    showNeedsToken: false,
  };
}

// "X ago" formatter used in the provisioning / error / grace cards.
// Pure function (no Date.now) so tests can pin the clock.
export function formatElapsed(
  now: number,
  iso: string,
  t: (key: string, params?: Record<string, unknown>) => string
): string {
  const parsed = Date.parse(iso);
  if (!Number.isFinite(parsed)) return "";
  const seconds = Math.max(0, Math.floor((now - parsed) / 1000));
  if (seconds < 60) return t("wa_elapsed_seconds", { count: seconds });
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return t("wa_elapsed_minutes", { count: minutes });
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return t("wa_elapsed_hours", { count: hours });
  const days = Math.floor(hours / 24);
  return t("wa_elapsed_days", { count: days });
}
