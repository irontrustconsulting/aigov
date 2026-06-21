/**
 * FE-7 / INV-25 / INV-32: lifecycle/gate-vector/coverage/authorisation reads
 * are non-cacheable verdicts. This registry is the single source of truth
 * for which query keys are "live state" — consulted by useLiveState's type
 * constraint AND by the no-raw-live-state-query ESLint rule
 * (packages/eslint-plugin-irontrust), which duplicates this list because
 * lint rules run outside the TS build graph. Keep both in sync.
 */
export const LIVE_STATE_KEYS = [
  "lifecycle-state",
  "gate-vector",
  "control-coverage",
  "deployment-authorisation",
] as const;

export type LiveStateKey = (typeof LIVE_STATE_KEYS)[number];

export type LiveStateQueryKey = readonly [LiveStateKey, ...unknown[]];
