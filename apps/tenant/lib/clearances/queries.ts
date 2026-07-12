"use client";

import { useLiveState } from "@irontrust/api-client";
import type { ClearanceQueueRead } from "@irontrust/api-client";
import { api } from "@/lib/api";
import { clearanceQueueKey } from "./query-keys";

/**
 * UI-F10-CLEARANCE: vendor-grouped clearance status (GET /v1/clearance-queue,
 * gov:ALL). Live state (FE-7) — never cached. Callers must branch on
 * `useMe()` first and not mount this hook for a caller with zero governance
 * roles (same DF2-5 posture as `usePortfolio`).
 */
export function useClearanceQueue() {
  return useLiveState(clearanceQueueKey(), () =>
    api.get<ClearanceQueueRead>("/v1/clearance-queue")
  );
}
