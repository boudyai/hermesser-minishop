import { normalizedEmail } from "./formatters.js";

export type RenewalDeeplink = {
  tariffKey: string;
};

export function currentSearchParams() {
  return new URLSearchParams(window.location.search);
}

export function readEmailCodeLoginDeeplink() {
  const params = currentSearchParams();
  if (params.get("login") !== "email_code") return null;
  const emailHint = normalizedEmail(params.get("login_email") || "");
  if (!emailHint || !emailHint.includes("@")) return null;
  return emailHint;
}

export function hasEmailCodeLoginDeeplink() {
  return Boolean(readEmailCodeLoginDeeplink());
}

export function readRenewalDeeplink(): RenewalDeeplink | null {
  const params = currentSearchParams();
  const shouldRenew = params.get("after_login") === "renew" || params.get("renew") === "1";
  if (!shouldRenew) return null;
  return {
    tariffKey: String(params.get("renew_tariff") || "").trim(),
  };
}

export function stripRenewalLoginQueryFromUrl() {
  if (typeof window === "undefined") return;
  const url = new URL(window.location.href);
  const keys = ["login", "login_email", "after_login", "renew", "renew_tariff"];
  const changed = keys.some((key) => url.searchParams.has(key));
  if (!changed) return;
  for (const key of keys) url.searchParams.delete(key);
  const search = url.searchParams.toString();
  window.history.replaceState(null, "", `${url.pathname}${search ? `?${search}` : ""}${url.hash}`);
}

export function stripTopupQueryFromUrl() {
  if (typeof window === "undefined") return;
  const url = new URL(window.location.href);
  if (!url.searchParams.has("topup")) return;
  url.searchParams.delete("topup");
  const search = url.searchParams.toString();
  window.history.replaceState(null, "", `${url.pathname}${search ? `?${search}` : ""}${url.hash}`);
}
