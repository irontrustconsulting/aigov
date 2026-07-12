/** Query key for the clearance-queue surface (UI-F10-CLEARANCE). Live-state
 * read (FE-7) — must satisfy `LiveStateQueryKey` (`@irontrust/api-client`),
 * enforced by the `no-raw-live-state-query` eslint rule. */
export function clearanceQueueKey() {
  return ["clearance-queue"] as const;
}
