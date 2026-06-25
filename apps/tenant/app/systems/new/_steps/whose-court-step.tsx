"use client";

import { ErrorState, PageHeader, PageScaffold, Skeleton } from "@irontrust/ui";
import { useUseCaseLifecycle } from "@/lib/intake";

/**
 * WI-9: GET /v1/use-cases/{id}/lifecycle via useLiveState (FE-7). Replaces
 * the F0 generic-pill WhoseCourtIndicator with real semantics, sourced from
 * `blocking` (the first non-advance gate, app/services/lifecycle_gates.py)
 * — never from a `/approval-status`-shaped read (confirmed absent at
 * pre-flight, C-3). Terminal screen for F1.
 */
const RESPONSIBLE_PARTY_COPY: Record<string, string> = {
  authoriser: "With the authoriser — vendor/product clearance is needed before this can proceed.",
  user: "With you — start the assessment to continue.",
  reviewer: "With the reviewer — your classification answers are pending review.",
};

export function WhoseCourtStep({ useCaseId }: { useCaseId: string }) {
  const lifecycle = useUseCaseLifecycle(useCaseId);

  if (lifecycle.isLoading) return <Skeleton />;
  if (lifecycle.isError || !lifecycle.data) {
    return (
      <ErrorState
        message="Could not load the current status."
        onRetry={() => lifecycle.refetch()}
      />
    );
  }

  const { blocking } = lifecycle.data;

  if (!blocking) {
    return (
      <PageScaffold>
        <section aria-label="whose-court">
          <PageHeader title="Use case status" />
          <p className="text-sm text-ink-muted">Nothing is blocking this use case right now.</p>
        </section>
      </PageScaffold>
    );
  }

  const headline =
    RESPONSIBLE_PARTY_COPY[blocking.responsible_party] ?? `With ${blocking.responsible_party}.`;

  return (
    <PageScaffold>
      <section aria-label="whose-court">
        <PageHeader title="Use case status" />
        <p className="text-sm">{headline}</p>
        <p className="text-sm text-ink-muted">{blocking.reason}</p>
      </section>
    </PageScaffold>
  );
}
