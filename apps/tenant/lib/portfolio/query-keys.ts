/** Query keys for the portfolio surface (UI-F2-PORTFOLIO). Portfolio and
 * system-rollup are live-state reads (FE-7) — their keys must satisfy
 * `LiveStateQueryKey` (`@irontrust/api-client`), enforced by the
 * `no-raw-live-state-query` eslint rule. `systems` is a low-churn registry
 * list, same treatment as F1's reference-data reads (plain `useQuery`). */
export function portfolioKey() {
  return ["portfolio"] as const;
}

export function systemRollupKey(systemId: string) {
  return ["system-rollup", systemId] as const;
}

export const portfolioKeys = {
  systems: () => ["systems"] as const,
} as const;
