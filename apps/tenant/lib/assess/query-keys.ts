/**
 * UI-F3-ASSESS query keys. lifecycleKey is NOT redefined here — import it
 * from lib/intake (same key instance = same TanStack cache, which is required
 * for invalidation after mutations that affect lifecycle state).
 */
export const assessKeys = {
  detail: (useCaseId: string) => ["assess", useCaseId] as const,
  assessments: (useCaseId: string) => ["assessments", useCaseId] as const,
  assessment: (assessmentId: string) => ["assessment", assessmentId] as const,
  sections: (assessmentId: string) => ["assessment-sections", assessmentId] as const,
  feederRecs: (assessmentId: string) => ["feeder-recs", assessmentId] as const,
  risks: () => ["reference-risks"] as const,
  controls: () => ["reference-controls"] as const,
  reviewQueue: () => ["review-queue"] as const,
  authorisation: (useCaseId: string) => ["authorisation", useCaseId] as const,
} as const;
