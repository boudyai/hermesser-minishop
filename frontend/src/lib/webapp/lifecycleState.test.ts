import { describe, expect, it } from "vitest";

import { deriveLifecycleView, formatElapsed } from "./lifecycleState.js";

const base = {
  hermesMode: true,
  hasBotToken: true,
  active: false,
  tenantStatus: null,
};

describe("deriveLifecycleView", () => {
  describe("out of scope", () => {
    it("hides the wizard in non-hermes mode", () => {
      const view = deriveLifecycleView({ ...base, hermesMode: false });
      expect(view.state).toBe("hidden");
      expect(view.showWizard).toBe(false);
    });

    it("hides the wizard when the subscription is already active", () => {
      const view = deriveLifecycleView({ ...base, active: true });
      expect(view.state).toBe("hidden");
      expect(view.showWizard).toBe(false);
    });

    it("hides the wizard when both non-hermes and active", () => {
      const view = deriveLifecycleView({
        hermesMode: false,
        hasBotToken: true,
        active: true,
        tenantStatus: "active",
      });
      expect(view.state).toBe("hidden");
    });
  });

  describe("needs token (no token yet)", () => {
    it("shows the wizard when in hermes mode without a token", () => {
      const view = deriveLifecycleView({ ...base, hasBotToken: false });
      expect(view.state).toBe("needs_token");
      expect(view.showWizard).toBe(true);
      expect(view.showNeedsToken).toBe(true);
    });

    it("does not pick a specific state when token is missing", () => {
      const view = deriveLifecycleView({ ...base, hasBotToken: false });
      expect(view.showProvisioning).toBe(false);
      expect(view.showError).toBe(false);
      expect(view.showGracePeriod).toBe(false);
      expect(view.showSuspended).toBe(false);
      expect(view.showDeleting).toBe(false);
    });
  });

  describe("provisioning in progress", () => {
    for (const status of [
      "created",
      "awaiting_payment",
      "paid",
      "provisioning_litellm_key",
      "provisioning_vm",
    ]) {
      it(`renders the provisioning card for status=${status}`, () => {
        const view = deriveLifecycleView({ ...base, tenantStatus: status });
        expect(view.state).toBe("provisioning");
        expect(view.showWizard).toBe(true);
        expect(view.showProvisioning).toBe(true);
        for (const other of [
          "showError",
          "showGracePeriod",
          "showSuspended",
          "showDeleting",
          "showNeedsToken",
        ]) {
          // @ts-expect-error -- dynamic index for compactness
          expect(view[other]).toBe(false);
        }
      });
    }
  });

  describe("error state", () => {
    it("renders the error card for status=error", () => {
      const view = deriveLifecycleView({ ...base, tenantStatus: "error" });
      expect(view.state).toBe("error");
      expect(view.showWizard).toBe(true);
      expect(view.showError).toBe(true);
      expect(view.showProvisioning).toBe(false);
    });
  });

  describe("grace period (payment_expiring)", () => {
    it("renders the grace period card", () => {
      const view = deriveLifecycleView({ ...base, tenantStatus: "payment_expiring" });
      expect(view.state).toBe("grace_period");
      expect(view.showWizard).toBe(true);
      expect(view.showGracePeriod).toBe(true);
      expect(view.showError).toBe(false);
    });
  });

  describe("suspended", () => {
    it("renders the suspended card", () => {
      const view = deriveLifecycleView({ ...base, tenantStatus: "suspended" });
      expect(view.state).toBe("suspended");
      expect(view.showWizard).toBe(true);
      expect(view.showSuspended).toBe(true);
    });
  });

  describe("deleting", () => {
    it("renders the deleting card", () => {
      const view = deriveLifecycleView({ ...base, tenantStatus: "deleting" });
      expect(view.state).toBe("deleting");
      expect(view.showWizard).toBe(true);
      expect(view.showDeleting).toBe(true);
    });
  });

  describe("unknown / missing status", () => {
    it("hides the wizard when token is already saved and status is null", () => {
      const view = deriveLifecycleView({ ...base, tenantStatus: null });
      expect(view.state).toBe("hidden");
      expect(view.showWizard).toBe(false);
      expect(view.showNeedsToken).toBe(false);
    });

    it("hides the wizard when token is already saved and status is empty string", () => {
      const view = deriveLifecycleView({ ...base, tenantStatus: "" });
      expect(view.state).toBe("hidden");
    });

    it("hides the wizard for unrecognised status values when token is already saved", () => {
      // "weird-state" isn't a TenantStatus enum value; treat as unknown.
      const view = deriveLifecycleView({ ...base, tenantStatus: "weird-state" });
      expect(view.state).toBe("hidden");
    });
  });

  describe("invariant: exactly one show* flag is true at a time", () => {
    const cases = [
      { name: "needs_token", hasBotToken: false },
      { name: "provisioning", tenantStatus: "provisioning_vm" },
      { name: "error", tenantStatus: "error" },
      { name: "grace_period", tenantStatus: "payment_expiring" },
      { name: "suspended", tenantStatus: "suspended" },
      { name: "deleting", tenantStatus: "deleting" },
    ];
    for (const c of cases) {
      it(`${c.name}: only one show* flag is true`, () => {
        const view = deriveLifecycleView({ ...base, ...c });
        const trueFlags = [
          view.showNeedsToken,
          view.showProvisioning,
          view.showError,
          view.showGracePeriod,
          view.showSuspended,
          view.showDeleting,
        ].filter(Boolean);
        expect(trueFlags).toHaveLength(1);
      });
    }
  });
});

describe("formatElapsed", () => {
  const now = Date.parse("2026-07-02T12:00:00Z");

  it("returns empty string for invalid input", () => {
    expect(formatElapsed(now, "")).toBe("");
    expect(formatElapsed(now, "not-a-date")).toBe("");
  });

  it("formats sub-minute deltas as seconds", () => {
    const t = new Date(now - 30 * 1000).toISOString();
    expect(formatElapsed(now, t)).toBe("30 сек назад");
  });

  it("formats sub-hour deltas as minutes", () => {
    const t = new Date(now - 5 * 60 * 1000).toISOString();
    expect(formatElapsed(now, t)).toBe("5 мин назад");
  });

  it("formats sub-day deltas as hours", () => {
    const t = new Date(now - 3 * 60 * 60 * 1000).toISOString();
    expect(formatElapsed(now, t)).toBe("3 ч назад");
  });

  it("formats multi-day deltas as days", () => {
    const t = new Date(now - 2 * 24 * 60 * 60 * 1000).toISOString();
    expect(formatElapsed(now, t)).toBe("2 дн назад");
  });

  it("clamps negative deltas to zero (clock skew safety)", () => {
    const t = new Date(now + 5 * 1000).toISOString();
    expect(formatElapsed(now, t)).toBe("0 сек назад");
  });
});
