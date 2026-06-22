"use client";

import { useQuery } from "@tanstack/react-query";
import type {
  CoverageMatrixRead,
  SystemExportRead,
  UseCaseExportRead,
  FrameworkExportRead,
  AtoDocumentRead,
} from "@irontrust/api-client";
import { api } from "@/lib/api";
import { auditKeys } from "./query-keys";

// ---------------------------------------------------------------------------
// Coverage hooks — eager, staleTime: 0 (FE-7 / NB5)
// Coverage emits no audit event (INV-42 / DF6-2); no deliberate-only constraint.
// ---------------------------------------------------------------------------

function buildCoverageParams(framework?: string, includeUnapproved?: boolean): string {
  const params = new URLSearchParams();
  if (framework) params.set("framework", framework);
  if (includeUnapproved) params.set("include_unapproved", "true");
  const str = params.toString();
  return str ? `?${str}` : "";
}

/** GET /v1/coverage — tenant-wide matrix, staleTime: 0. */
export function useTenantCoverage(framework?: string, includeUnapproved = false) {
  return useQuery({
    queryKey: auditKeys.tenantCoverage(framework, includeUnapproved),
    queryFn: () =>
      api.get<CoverageMatrixRead>(`/v1/coverage${buildCoverageParams(framework, includeUnapproved)}`),
    staleTime: 0,
  });
}

/** GET /v1/systems/{id}/coverage — per-system matrix, staleTime: 0. */
export function useSystemCoverage(systemId: string, framework?: string, includeUnapproved = false) {
  return useQuery({
    queryKey: auditKeys.systemCoverage(systemId, framework, includeUnapproved),
    queryFn: () =>
      api.get<CoverageMatrixRead>(
        `/v1/systems/${systemId}/coverage${buildCoverageParams(framework, includeUnapproved)}`
      ),
    enabled: Boolean(systemId),
    staleTime: 0,
  });
}

/** GET /v1/assessments/{id}/coverage — per-AIIA matrix, staleTime: 0.
 * Call only when the governing AIIA is APPROVED (INV-38/DF3-2); gate at call site. */
export function useUseCaseCoverage(
  assessmentId: string,
  framework?: string,
  includeUnapproved = false
) {
  return useQuery({
    queryKey: auditKeys.useCaseCoverage(assessmentId, framework, includeUnapproved),
    queryFn: () =>
      api.get<CoverageMatrixRead>(
        `/v1/assessments/${assessmentId}/coverage${buildCoverageParams(framework, includeUnapproved)}`
      ),
    enabled: Boolean(assessmentId),
    staleTime: 0,
  });
}

// ---------------------------------------------------------------------------
// Export hooks — deliberate-only (INV-53)
// Stages export.generated; must NEVER fire on mount or window focus.
// ---------------------------------------------------------------------------

/** GET /v1/systems/{id}/export — deliberate only. `enabled` controls firing.
 * staleTime: Infinity + refetchOnWindowFocus: false prevent re-disclosure. */
export function useSystemExport(systemId: string, enabled: boolean, framework?: string) {
  return useQuery({
    queryKey: auditKeys.systemExport(systemId, framework),
    queryFn: () =>
      api.get<SystemExportRead>(
        `/v1/systems/${systemId}/export${framework ? `?framework=${framework}` : ""}`
      ),
    enabled,
    staleTime: Infinity,
    refetchOnWindowFocus: false,
    refetchOnMount: false,
  });
}

/** GET /v1/use-cases/{id}/export — deliberate only. */
export function useUseCaseExport(useCaseId: string, enabled: boolean, framework?: string) {
  return useQuery({
    queryKey: auditKeys.useCaseExport(useCaseId, framework),
    queryFn: () =>
      api.get<UseCaseExportRead>(
        `/v1/use-cases/${useCaseId}/export${framework ? `?framework=${framework}` : ""}`
      ),
    enabled,
    staleTime: Infinity,
    refetchOnWindowFocus: false,
    refetchOnMount: false,
  });
}

/** GET /v1/export?framework= — deliberate only. */
export function useFrameworkExport(framework: string, enabled: boolean) {
  return useQuery({
    queryKey: auditKeys.frameworkExport(framework),
    queryFn: () =>
      api.get<FrameworkExportRead>(`/v1/export?framework=${framework}`),
    enabled: Boolean(framework) && enabled,
    staleTime: Infinity,
    refetchOnWindowFocus: false,
    refetchOnMount: false,
  });
}

/** GET /v1/use-cases/{id}/authorisation/document — deliberate only.
 * 404 = never authorised; caller renders empty-state (retry: false). */
export function useAtoDocument(useCaseId: string, enabled: boolean, round?: number) {
  return useQuery({
    queryKey: auditKeys.atoDocument(useCaseId, round),
    queryFn: () =>
      api.get<AtoDocumentRead>(
        `/v1/use-cases/${useCaseId}/authorisation/document${round !== undefined ? `?round=${round}` : ""}`
      ),
    enabled,
    staleTime: Infinity,
    refetchOnWindowFocus: false,
    refetchOnMount: false,
    retry: (failureCount, error) => {
      if ((error as { status?: number }).status === 404) return false;
      return failureCount < 3;
    },
  });
}
