"use client";

import { useQuery } from "@tanstack/react-query";
import { useLiveState } from "@irontrust/api-client";
import type { SystemRead, SystemRollupRead } from "@irontrust/api-client";
import { api } from "@/lib/api";
import { portfolioKey, portfolioKeys, systemRollupKey } from "./query-keys";

/**
 * UI-F2-PORTFOLIO: tenant-wide rollup, one entry per system with >=1 use
 * case (GET /v1/portfolio, gov:ALL). Live state (FE-7) — never cached.
 * Callers must branch on `useMe()` first and not mount this hook for an
 * admin-only caller (DF2-5 — proactive branch, no gov:ALL request issued).
 */
export function usePortfolio() {
  return useLiveState(portfolioKey(), () => api.get<SystemRollupRead[]>("/v1/portfolio"));
}

/** GET /v1/systems/{id}/rollup (gov:ALL) — the system drill-in. Live state. */
export function useSystemRollup(systemId: string) {
  return useLiveState(systemRollupKey(systemId), () =>
    api.get<SystemRollupRead>(`/v1/systems/${systemId}/rollup`)
  );
}

/** GET /v1/systems (any member) — backs the A2 zero-use-case empty-card
 * merge. Cached, not live-state: a system registry list, not a verdict. */
export function useSystems() {
  return useQuery({
    queryKey: portfolioKeys.systems(),
    queryFn: () => api.get<SystemRead[]>("/v1/systems"),
  });
}
