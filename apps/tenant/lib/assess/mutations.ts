"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import type {
  AssessmentDetail,
  AssessmentItemAmend,
  AssessmentItemCreate,
  AssessmentItemRead,
  AssessmentRead,
  ControlLinkCreate,
  ControlLinkRead,
} from "@irontrust/api-client";
import { StaleLockError, BadFromStateError } from "@irontrust/api-client";
import { api } from "@/lib/api";
import { lifecycleKey } from "@/lib/intake/query-keys";
import { assessKeys } from "./query-keys";

// ---------------------------------------------------------------------------
// Bootstrap (WI-2) — gov:system_owner, no If-Match
// ---------------------------------------------------------------------------

export function useBootstrapAssessment(useCaseId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => api.post<AssessmentRead>(`/v1/use-cases/${useCaseId}/assessments`, {}),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: assessKeys.assessments(useCaseId) });
      queryClient.invalidateQueries({ queryKey: lifecycleKey(useCaseId) });
    },
  });
}

// ---------------------------------------------------------------------------
// Item authoring (WI-3) — gov:write, If-Match on PATCH/confirm
// ---------------------------------------------------------------------------

/**
 * PATCH .../items/{id} — amend authoring fields.
 * Sends If-Match with the item's current lock_version (FE-6/PAT-6).
 * 412 → stale lock (caller shows StaleLockBanner, invalidates to reload).
 * 409 → bad from-state, action void (BadFromStateBanner).
 */
export function useAmendItem(assessmentId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      itemId,
      body,
      lockVersion,
    }: {
      itemId: string;
      body: AssessmentItemAmend;
      lockVersion: number;
    }) =>
      api.patch<AssessmentItemRead, AssessmentItemAmend>(
        `/v1/assessments/${assessmentId}/items/${itemId}`,
        body,
        { lockVersion: String(lockVersion) }
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: assessKeys.assessment(assessmentId) });
    },
  });
}

/**
 * POST .../items/{id}/confirm — disposition an AI_SUGGESTED item.
 * Sends If-Match. Same 412/409 distinction as amend.
 */
export function useConfirmItem(assessmentId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ itemId, lockVersion }: { itemId: string; lockVersion: number }) =>
      api.post<AssessmentItemRead>(
        `/v1/assessments/${assessmentId}/items/${itemId}/confirm`,
        {},
        { lockVersion: String(lockVersion) }
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: assessKeys.assessment(assessmentId) });
    },
  });
}

// ---------------------------------------------------------------------------
// Item create / delete (WI-4) — gov:write, no If-Match
// ---------------------------------------------------------------------------

export function useCreateItem(assessmentId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: AssessmentItemCreate) =>
      api.post<AssessmentItemRead, AssessmentItemCreate>(
        `/v1/assessments/${assessmentId}/items`,
        body
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: assessKeys.assessment(assessmentId) });
      queryClient.invalidateQueries({ queryKey: assessKeys.sections(assessmentId) });
    },
  });
}

export function useDeleteItem(assessmentId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (itemId: string) =>
      api.delete<void>(`/v1/assessments/${assessmentId}/items/${itemId}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: assessKeys.assessment(assessmentId) });
    },
  });
}

// ---------------------------------------------------------------------------
// Control links (WI-5) — gov:write, no If-Match; free on any item
// ---------------------------------------------------------------------------

export function useCreateControlLink(assessmentId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ itemId, body }: { itemId: string; body: ControlLinkCreate }) =>
      api.post<ControlLinkRead, ControlLinkCreate>(
        `/v1/assessments/${assessmentId}/items/${itemId}/control-links`,
        body
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: assessKeys.assessment(assessmentId) });
    },
  });
}

export function useDeleteControlLink(assessmentId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ itemId, linkId }: { itemId: string; linkId: string }) =>
      api.delete<void>(`/v1/assessments/${assessmentId}/items/${itemId}/control-links/${linkId}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: assessKeys.assessment(assessmentId) });
    },
  });
}

// ---------------------------------------------------------------------------
// Submit (WI-6) — gov:system_owner, If-Match on assessment.lock_version
// ---------------------------------------------------------------------------

/**
 * POST .../submit — DRAFT/NEEDS_REFRESH → IN_REVIEW.
 * Sends If-Match on the assessment's lock_version (not an item's).
 * On success: lifecycle invalidated (court moves to reviewer).
 */
export function useSubmitAssessment(useCaseId: string, assessmentId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (lockVersion: number) =>
      api.post<AssessmentRead>(
        `/v1/assessments/${assessmentId}/submit`,
        {},
        { lockVersion: String(lockVersion) }
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: assessKeys.assessment(assessmentId) });
      queryClient.invalidateQueries({ queryKey: assessKeys.assessments(useCaseId) });
      queryClient.invalidateQueries({ queryKey: lifecycleKey(useCaseId) });
    },
  });
}

// ---------------------------------------------------------------------------
// Re-evaluate lever (WI-1) — gov:system_owner, no If-Match
// ---------------------------------------------------------------------------

export function useReEvaluate(useCaseId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () =>
      api.post<unknown>(`/v1/use-cases/${useCaseId}/lifecycle/re-evaluate`, {}),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: lifecycleKey(useCaseId) });
    },
  });
}

// ---------------------------------------------------------------------------
// Error type re-exports for caller instanceof checks (FE-6)
// ---------------------------------------------------------------------------
export { StaleLockError, BadFromStateError };
