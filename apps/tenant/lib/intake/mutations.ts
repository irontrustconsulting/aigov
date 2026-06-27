"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import type {
  ComputeRequest,
  ComputeResultRead,
  ContextOutcomeRead,
  OverrideRequest,
  PreviewRequest,
  RegistrationCreate,
  RegistrationRead,
  UseCaseWithClassification,
} from "@irontrust/api-client";
import { api } from "@/lib/api";
import { lifecycleKey } from "./query-keys";

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
