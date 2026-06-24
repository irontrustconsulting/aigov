"use client";

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

  if (lifecycle.isLoading) return <p>Loading status…</p>;
  if (lifecycle.isError || !lifecycle.data) return <p role="alert">Could not load the current status.</p>;

  const { blocking } = lifecycle.data;

  if (!blocking) {
    return (
      <section aria-label="whose-court" className="mx-auto max-w-4xl space-y-4 px-6 py-8">
        <p className="text-ink-muted text-sm">Nothing is blocking this use case right now.</p>
      </section>
    );
  }

  const headline =
    RESPONSIBLE_PARTY_COPY[blocking.responsible_party] ?? `With ${blocking.responsible_party}.`;

  return (
    <section aria-label="whose-court" className="mx-auto max-w-4xl space-y-4 px-6 py-8">
      <p className="text-sm">{headline}</p>
      <p className="text-ink-muted text-sm">{blocking.reason}</p>
    </section>
  );
}
