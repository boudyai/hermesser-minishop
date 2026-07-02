import { DATASET, defaultClone, type DemoRecord, type DemoTicket } from "./dataset";

let demoPromosState: DemoRecord[] | null = null;
let demoAdsState: DemoRecord[] | null = null;
let demoSupportTicketsState: DemoTicket[] | null = null;
let demoSupportMessagesState: Record<string, DemoRecord[]> | null = null;
let demoTariffsState: DemoRecord | null = null;
let demoPaymentSequence = 20000;

export const demoSettingsChanges = new Map<string, { value?: unknown; deleted: boolean }>();

export type DemoPaymentStatus = {
  status: string;
  paid: boolean;
  sale_mode: string;
  device_count: number;
  applied: boolean;
};

export const demoPaymentStatuses = new Map<string, DemoPaymentStatus>();

const deviceTopupSaleModes = new Set(["hwid_device", "hwid_devices", "hwid_devices_renewal"]);

export function isDeviceTopupSaleMode(value: unknown): boolean {
  return deviceTopupSaleModes.has(String(value || "").toLowerCase());
}

export function nextDemoPaymentId(): number {
  return ++demoPaymentSequence;
}

export function demoPromos(): DemoRecord[] {
  if (!demoPromosState) demoPromosState = defaultClone(DATASET.promos || []);
  return demoPromosState;
}

export function setDemoPromos(next: DemoRecord[]): void {
  demoPromosState = next;
}

export function demoAds(): DemoRecord[] {
  if (!demoAdsState) demoAdsState = defaultClone(DATASET.ads || []);
  return demoAdsState;
}

export function setDemoAds(next: DemoRecord[]): void {
  demoAdsState = next;
}

export function demoSupportTickets(): DemoTicket[] {
  if (!demoSupportTicketsState) {
    demoSupportTicketsState = defaultClone(DATASET.supportTickets || []);
  }
  return demoSupportTicketsState;
}

export function demoSupportMessages(): Record<string, DemoRecord[]> {
  if (!demoSupportMessagesState) {
    demoSupportMessagesState = defaultClone(DATASET.supportMessages || {});
  }
  return demoSupportMessagesState;
}

export function demoTariffs(): DemoRecord {
  if (!demoTariffsState) {
    demoTariffsState = defaultClone(
      DATASET.tariffsCatalog || {
        default_tariff: "",
        topup_packages_default: { rub: [], stars: [] },
        tariffs: [],
      }
    );
  }
  return demoTariffsState;
}

export function setDemoTariffs(next: DemoRecord): void {
  demoTariffsState = next;
}
