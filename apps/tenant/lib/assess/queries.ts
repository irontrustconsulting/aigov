"use client";

import { useQuery } from "@tanstack/react-query";
import type {
  AssessmentDetail,
  AssessmentRead,
  ControlRead,
  DeploymentAuthorisationRead,
  FeederRecommendationRead,
  ReviewQueueEntryRead,
  RiskRead,
  SectionRead,
  UseCaseWithClassification,
} from "@irontrust/api-client";
import { api } from "@/lib/api";
import { assessKeys } from "./query-keys";

// Re-export useMe and useUseCaseLifecycle so callers import from one place.
export { useMe } from "@/lib/intake";
export { useUseCaseLifecycle } from "@/lib/intake";

/** GET /v1/use-cases/{id} — identity + classification for the header. */
export function useUseCaseDetail(useCaseId: string) {
  return useQuery({
    queryKey: assessKeys.detail(useCaseId),
    queryFn: () => api.get<UseCaseWithClassification>(`/v1/use-cases/${useCaseId}`),
    enabled: Boolean(useCaseId),
  });
}

/** GET /v1/use-cases/{id}/assessments — list (0 or 1 current AIIA). */
export function useAssessments(useCaseId: string) {
  return useQuery({
    queryKey: assessKeys.assessments(useCaseId),
    queryFn: () => api.get<AssessmentRead[]>(`/v1/use-cases/${useCaseId}/assessments`),
    enabled: Boolean(useCaseId),
  });
}

/**
 * GET /v1/assessments/{id} — assembled AIIA with items + control_links.
 * staleTime: 0 (FE-7/INV-25): assessment body is a consequential verdict;
 * never serve a cached snapshot to an authoring view.
 */
export function useAssessmentDetail(assessmentId: string) {
  return useQuery({
    queryKey: assessKeys.assessment(assessmentId),
    queryFn: () => api.get<AssessmentDetail>(`/v1/assessments/${assessmentId}`),
    enabled: Boolean(assessmentId),
    staleTime: 0,
  });
}

/** GET /v1/assessments/{id}/sections — tier-scoped section template. */
export function useAssessmentSections(assessmentId: string) {
  return useQuery({
    queryKey: assessKeys.sections(assessmentId),
    queryFn: () => api.get<SectionRead[]>(`/v1/assessments/${assessmentId}/sections`),
    enabled: Boolean(assessmentId),
  });
}

/** GET /v1/assessments/{id}/feeder-recommendations — read-only (A7). */
export function useFeederRecs(assessmentId: string) {
  return useQuery({
    queryKey: assessKeys.feederRecs(assessmentId),
    queryFn: () =>
      api.get<FeederRecommendationRead[]>(`/v1/assessments/${assessmentId}/feeder-recommendations`),
    enabled: Boolean(assessmentId),
  });
}

/** GET /v1/reference/risks — risk library for item authoring pickers. */
export function useRisks() {
  return useQuery({
    queryKey: assessKeys.risks(),
    queryFn: () => api.get<RiskRead[]>("/v1/reference/risks"),
  });
}

/** GET /v1/reference/controls — control library for control-link pickers. */
export function useControls() {
  return useQuery({
    queryKey: assessKeys.controls(),
    queryFn: () => api.get<ControlRead[]>("/v1/reference/controls"),
  });
}

// ---------------------------------------------------------------------------
// UI-F4-ASSURE queries
// ---------------------------------------------------------------------------

/** GET /v1/assessments/review-queue — gov:reviewer; call only when caller is a reviewer. */
export function useReviewQueue() {
  return useQuery({
    queryKey: assessKeys.reviewQueue(),
    queryFn: () => api.get<ReviewQueueEntryRead[]>("/v1/assessments/review-queue"),
  });
}

/**
 * GET /v1/use-cases/{id}/authorisation — most-recent ATO + computed live_state.
 * staleTime: 0 (FE-7): live_state is consequential; never serve a cached snapshot.
 * 404 = use case has never been authorised (caller renders nothing).
 */
export function useAuthorisation(useCaseId: string) {
  return useQuery({
    queryKey: assessKeys.authorisation(useCaseId),
    queryFn: () => api.get<DeploymentAuthorisationRead>(`/v1/use-cases/${useCaseId}/authorisation`),
    enabled: Boolean(useCaseId),
    staleTime: 0,
    retry: (failureCount, error) => {
      if ((error as { status?: number }).status === 404) return false;
      return failureCount < 3;
    },
  });
}
