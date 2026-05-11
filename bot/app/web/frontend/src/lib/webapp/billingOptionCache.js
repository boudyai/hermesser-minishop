/** Drop cached topup / change-tariff option payloads so the next open refetches from /api. */
export function invalidateWebappTariffOptionCaches(billingStore) {
  billingStore.update((s) => ({ ...s, topupOptions: null, deviceTopupOptions: null, changeOptions: null }));
}
