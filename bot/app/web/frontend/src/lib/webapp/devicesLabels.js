/**
 * Pure helpers for HWID / device limits UI (used by DevicesScreen).
 * @param {Record<string, unknown>} devicesData API payload from /api/devices
 * @param {(key: string, vars?: Record<string, unknown>, fallback?: string) => string} t i18n function
 * @param {unknown} [maxDevicesOverride] optional max_devices override (defaults to devicesData.max_devices)
 */
export function devicesLimitLabel(devicesData, t, maxDevicesOverride) {
  const value = maxDevicesOverride !== undefined ? maxDevicesOverride : devicesData?.max_devices;
  const numeric = Number(value ?? 0);
  if (!Number.isFinite(numeric) || numeric <= 0) return t("wa_devices_unlimited");
  return String(Math.trunc(numeric));
}

export function devicesCountLabel(devicesData, t) {
  const current = Number(devicesData?.current_devices ?? devicesData?.devices?.length ?? 0);
  return t("wa_devices_count", { current, max: devicesLimitLabel(devicesData, t) });
}

export function devicesPercent(devicesData) {
  const current = Number(devicesData?.current_devices ?? devicesData?.devices?.length ?? 0);
  const max = Number(devicesData?.max_devices || 0);
  if (!max || max <= 0) return 100;
  return Math.max(0, Math.min(100, Math.round((current / max) * 100)));
}
