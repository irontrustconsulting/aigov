"use client";

import { useQuery } from "@tanstack/react-query";
import type { EvidenceDetailRead, EvidenceListResponse } from "@irontrust/api-client";
import { api } from "@/lib/api";
import { evidenceKeys } from "./query-keys";

/** GET /v1/evidence?limit=50 — paginated list with link_count. */
export function useEvidenceList() {
  return useQuery({
    queryKey: evidenceKeys.list(),
    queryFn: () => api.get<EvidenceListResponse>("/v1/evidence?limit=50"),
  });
}

/**
 * GET /v1/evidence/{id} — detail with presigned download_url.
 * `enabled=false` by default; set true only on explicit download intent (DF5-3).
 * Stages evidence.access — never pre-fetched per row.
 */
export function useEvidenceDetail(id: string, enabled: boolean) {
  return useQuery({
    queryKey: evidenceKeys.detail(id),
    queryFn: () => api.get<EvidenceDetailRead>(`/v1/evidence/${id}`),
    enabled,
    staleTime: 0,
    retry: false,
  });
}
