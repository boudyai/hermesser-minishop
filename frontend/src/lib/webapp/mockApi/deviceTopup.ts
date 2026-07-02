import { DEV_MOCK } from "../previewMock.js";
import type { DemoRecord } from "./dataset";

type DeviceTopupBody = DemoRecord & {
  device_count?: unknown;
  months?: unknown;
  tariff_key?: unknown;
};

type DeviceTopupPlan = DemoRecord & {
  tariff_key?: unknown;
  device_count?: unknown;
  purchased_hwid_devices?: unknown;
  months?: unknown;
};

export function demoDeviceTopupPlan(body: DeviceTopupBody): DeviceTopupPlan | null {
  const deviceCount = Number(body.device_count || body.months || 0);
  const plans = ((DEV_MOCK.data.device_topup_options?.plans as DeviceTopupPlan[] | undefined) ||
    []) as DeviceTopupPlan[];
  return (
    plans.find(
      (plan) =>
        String(plan.tariff_key || "") === String(body.tariff_key || plan.tariff_key || "") &&
        Number(plan.device_count || plan.purchased_hwid_devices || plan.months || 0) === deviceCount
    ) ||
    plans.find(
      (plan) =>
        Number(plan.device_count || plan.purchased_hwid_devices || plan.months || 0) === deviceCount
    ) ||
    null
  );
}

export function applyDemoDeviceTopup(deviceCount: number): void {
  const count = Math.max(1, Number(deviceCount || 0));
  const subscription = DEV_MOCK.data.subscription || {};
  const devicesPayload = DEV_MOCK.data.devices || {};
  const topupOptions = DEV_MOCK.data.device_topup_options || {};
  const devices = Array.isArray(devicesPayload.devices) ? devicesPayload.devices : [];
  const currentMax = Number(
    subscription.max_devices ||
      devicesPayload.max_devices ||
      topupOptions.max_devices ||
      topupOptions.current_limit ||
      0
  );
  const nextMax = currentMax > 0 ? currentMax + count : currentMax;
  const currentExtra = Number(
    subscription.extra_hwid_devices || topupOptions.extra_hwid_devices || 0
  );
  const nextExtra = currentExtra + count;
  const validUntil =
    subscription.extra_hwid_devices_valid_until_text ||
    topupOptions.extra_hwid_devices_valid_until_text ||
    subscription.end_date_text ||
    "28.06.2026 12:00";

  DEV_MOCK.data.subscription = {
    ...subscription,
    active: true,
    can_topup_devices: true,
    max_devices: nextMax,
    extra_hwid_devices: nextExtra,
    extra_hwid_devices_valid_until_text: validUntil,
  };
  DEV_MOCK.data.devices = {
    ...devicesPayload,
    ok: true,
    enabled: true,
    current_devices: devices.length || Number(devicesPayload.current_devices || 0),
    max_devices: nextMax,
    max_devices_label:
      nextMax > 0 ? String(nextMax) : (devicesPayload.max_devices_label as string) || "∞",
  };
  DEV_MOCK.data.device_topup_options = {
    ...topupOptions,
    ok: true,
    enabled: true,
    current_devices: devices.length || Number(topupOptions.current_devices || 0),
    max_devices: nextMax,
    current_limit: nextMax,
    extra_hwid_devices: nextExtra,
    extra_hwid_devices_valid_until_text: validUntil,
  };
}
