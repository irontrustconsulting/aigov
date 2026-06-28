"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import type {
  ComputeRequest,
  ComputeResultRead,
  ContextOutcomeRead,
  DraftRegistrationPatch,
  DraftRegistrationRead,
  OverrideRequest,
  PreviewRequest,
  RegistrationCreate,
  RegistrationRead,
  UseCaseWithClassification,
} from "@irontrust/api-client";
import { api } from "@/lib/api";
import { intakeKeys, lifecycleKey } from "./query-keys";

/**
 * WI-3: every mutation goes through `api` (the BFF client) — never a raw
 * fetch. None send `If-Match` (FE-6 is dormant in F1: no consumed route
 * here accepts it). After a write that can move the lifecycle state
 * (register, override, context submit), the lifecycle live-state query is
 * invalidated so WI-9 never reads a stale verdict (FE-7).
 */

export function useRegister() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: RegistrationCreate) =>
      api.post<RegistrationRead, RegistrationCreate>("/v1/registrations", body),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: lifecycleKey(data.use_case.id) });
      // Draft is atomically deleted on the backend; clear the client-side cache (D-66).
      queryClient.invalidateQueries({ queryKey: intakeKeys.activeDraft() });
    },
  });
}

// ---------------------------------------------------------------------------
// Draft mutations (DM-S3, D-66)
// ---------------------------------------------------------------------------

export function useGetOrCreateDraft() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => api.post<DraftRegistrationRead, Record<string, never>>("/v1/draft-registrations", {}),
    onSuccess: (data) => {
      queryClient.setQueryData(intakeKeys.activeDraft(), data);
    },
  });
}

export function usePatchDraft(draftId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: DraftRegistrationPatch) =>
      api.patch<DraftRegistrationRead, DraftRegistrationPatch>(
        `/v1/draft-registrations/${draftId}`,
        body
      ),
    onSuccess: (data) => {
      queryClient.setQueryData(intakeKeys.activeDraft(), data);
    },
  });
}

export function useDiscardDraft() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (draftId: string) =>
      api.delete<void>(`/v1/draft-registrations/${draftId}`),
    onSuccess: () => {
      queryClient.setQueryData(intakeKeys.activeDraft(), null);
    },
  });
}

export function useOverrideClassification(useCaseId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: OverrideRequest) =>
      api.post<UseCaseWithClassification, OverrideRequest>(
        `/v1/use-cases/${useCaseId}/classify/override`,
        body
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: lifecycleKey(useCaseId) });
    },
  });
}

export function usePreviewContext(useCaseId: string) {
  return useMutation({
    mutationFn: (body: PreviewRequest) =>
      api.post<ContextOutcomeRead, PreviewRequest>(
        `/v1/use-cases/${useCaseId}/classification/context/preview`,
        body
      ),
  });
}

export function useSubmitContext(useCaseId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: ComputeRequest) =>
      api.post<ComputeResultRead, ComputeRequest>(
        `/v1/use-cases/${useCaseId}/classification/context`,
        body
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: lifecycleKey(useCaseId) });
    },
  });
}
