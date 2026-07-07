type ActivationRecord = Record<string, unknown>;
type ActivationPendingState = ActivationRecord;
type ActivationAcknowledgedState = ActivationRecord;

interface ActivationState {
  pending?: ActivationPendingState | null;
  acknowledged?: ActivationAcknowledgedState | null;
}

interface ActivationHandoffOptions {
  storageKey?: string;
  ttlMs?: number;
  now?: () => number;
}

interface ActivationContext extends ActivationRecord {
  initialSubscriptionPayment?: boolean;
  source?: unknown;
  paymentId?: unknown;
}

function recordOrEmpty(value: unknown): ActivationRecord {
  return value && typeof value === "object" ? (value as ActivationRecord) : {};
}

function stateEntry(value: unknown): ActivationRecord | null {
  return value && typeof value === "object" ? (value as ActivationRecord) : null;
}

export function activationPaymentFailed(status: unknown): boolean {
  const statusRecord = recordOrEmpty(status);
  const normalized = String(statusRecord.status || "").toLowerCase();
  return (
    normalized === "failed" ||
    normalized === "canceled" ||
    normalized === "cancelled" ||
    normalized.startsWith("failed_")
  );
}

export function createActivationHandoff({
  storageKey,
  ttlMs,
  now = () => Date.now(),
}: ActivationHandoffOptions = {}) {
  let fallbackState: ActivationState | null = null;
  const ttl = Number(ttlMs || 0);

  function normalizeState(value: unknown): ActivationState {
    const state = recordOrEmpty(value);
    return value && typeof value === "object"
      ? {
          pending: stateEntry(state.pending) as ActivationPendingState | null,
          acknowledged:
            (stateEntry(state.acknowledged) as ActivationAcknowledgedState | null) || null,
        }
      : { pending: null, acknowledged: null };
  }

  function isPendingFresh(pending: ActivationPendingState | null | undefined): boolean {
    const startedAt = Number(pending?.startedAt || 0);
    return Boolean(startedAt && now() - startedAt <= ttl);
  }

  function write(state: ActivationState): void {
    const normalized = normalizeState(state);
    fallbackState = normalized;
    if (!storageKey) return;
    try {
      localStorage.setItem(storageKey, JSON.stringify(normalized));
    } catch (_error) {
      void _error;
    }
  }

  function read(): ActivationState {
    let state = fallbackState || { pending: null, acknowledged: null };
    if (storageKey) {
      try {
        const raw = localStorage.getItem(storageKey);
        if (raw) state = normalizeState(JSON.parse(raw));
      } catch (_error) {
        void _error;
      }
    }
    state = normalizeState(state);
    if (state.pending && !isPendingFresh(state.pending)) {
      state = { ...state, pending: null };
      write(state);
    }
    return state;
  }

  function userKey(payload: ActivationRecord = {}): string {
    const payloadUser = recordOrEmpty(payload.user);
    return String(payloadUser.user_id ?? payloadUser.id ?? payloadUser.telegram_id ?? "").trim();
  }

  function subscriptionKey(payload: ActivationRecord = {}): string {
    const payloadSubscription = recordOrEmpty(payload.subscription);
    if (!payloadSubscription?.active) return "";
    return [
      userKey(payload) || "anonymous",
      payloadSubscription.panel_short_uuid ||
        payloadSubscription.panel_uuid ||
        payloadSubscription.uuid ||
        payloadSubscription.subscription_id ||
        payloadSubscription.config_link ||
        payloadSubscription.connect_url ||
        "active",
      payloadSubscription.end_date || payloadSubscription.end_date_text || "",
      payloadSubscription.tariff_key || payloadSubscription.tariff_name || "",
      payloadSubscription.status || "",
    ]
      .map((part) => String(part || "").trim())
      .join("|");
  }

  function pendingMatchesUser(
    pending: ActivationPendingState | null | undefined,
    payload: ActivationRecord = {}
  ): boolean {
    if (!pending) return false;
    const pendingUserKey = String(pending.userKey || "").trim();
    const currentUserKey = userKey(payload);
    return !pendingUserKey || !currentUserKey || pendingUserKey === currentUserKey;
  }

  function hasPending(payload: ActivationRecord = {}): boolean {
    const pending = read().pending;
    return Boolean(pending && pendingMatchesUser(pending, payload));
  }

  function rememberPending(context: ActivationContext = {}, payload: ActivationRecord = {}): void {
    if (context.initialSubscriptionPayment === false) return;
    const state = read();
    write({
      ...state,
      pending: {
        kind: "initial_subscription",
        source: String(context.source || "payment"),
        paymentId: String(context.paymentId || ""),
        userKey: userKey(payload),
        startedAt: now(),
      },
    });
  }

  function clearPending(): void {
    const state = read();
    if (!state.pending) return;
    write({ ...state, pending: null });
  }

  function isAcknowledged(nextSubscriptionKey: string, state: ActivationState = read()): boolean {
    return Boolean(
      nextSubscriptionKey && state.acknowledged?.subscriptionKey === nextSubscriptionKey
    );
  }

  function acknowledge(
    nextSubscriptionKey: string,
    context: ActivationContext = {},
    payload: ActivationRecord = {},
    state: ActivationState = read()
  ): void {
    const pending = state.pending || {};
    write({
      ...state,
      pending: null,
      acknowledged: {
        subscriptionKey: nextSubscriptionKey,
        source: String(context.source || pending.source || "payment"),
        paymentId: String(context.paymentId || pending.paymentId || ""),
        userKey: userKey(payload),
        acknowledgedAt: now(),
      },
    });
  }

  return {
    acknowledge,
    clearPending,
    hasPending,
    isAcknowledged,
    isPendingFresh,
    pendingMatchesUser,
    read,
    rememberPending,
    subscriptionKey,
    write,
  };
}
