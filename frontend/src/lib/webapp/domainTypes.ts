import type { MeResponse } from "./publicApi";

export type WebappRecord = Record<string, unknown>;
export type WebappData = MeResponse & WebappRecord;

export type WebappBillingPlan = WebappRecord & {
  device_count?: number | string;
  hwid_renewal?: WebappRecord;
  months?: number | string;
  sale_mode?: string;
  tariff_key?: string;
  traffic_gb?: number | string;
};

export type WebappBillingAction = WebappRecord & {
  mode?: string;
  months?: number | string;
  traffic_gb?: number | string;
};

export type WebappBillingTarget = WebappRecord & {
  tariff_key?: string;
};

export function recordField(value: unknown): WebappRecord {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as WebappRecord) : {};
}

export function recordOrNull(value: unknown): WebappRecord | null {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as WebappRecord)
    : null;
}

export function arrayField(value: unknown): unknown[] {
  return Array.isArray(value) ? value : [];
}

export function recordArrayField(value: unknown): WebappRecord[] {
  return Array.isArray(value)
    ? value.filter((item): item is WebappRecord => Boolean(recordOrNull(item)))
    : [];
}

export function stringField(value: unknown): string {
  return typeof value === "string" ? value : "";
}
