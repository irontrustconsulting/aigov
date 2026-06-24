"use client";

import { useRouter } from "next/navigation";
import { useMe, useReviewQueue } from "@/lib/assess";
import { QueueRow, TierBadge, toTierMember } from "@irontrust/ui";

/**
 * Reviewer AIIA review queue (UI-F4-ASSURE WI-1).
 * GET /assessments/review-queue is issued ONLY when caller has "reviewer" role.
 * Non-reviewer (incl. auditor) renders an empty-state with no queue call (DF2-5 spirit).
 * Admin (zero governance roles) renders the same empty-state — no gov:ALL call.
 * Each row links forward to /use-cases/{use_case_id} (Topology B, DF4-1).
 * submitted_by_name from INV-34 join on the backend; never raw app_user.
 */
export function ReviewQueueClient() {
  const me = useMe();

  if (me.isLoading) return <p>Loading…</p>;
  if (me.isError || !me.data) return <p role="alert">Could not load your role.</p>;

  const isReviewer = me.data.governance_roles.some((r) => r.key === "reviewer");

  if (!isReviewer) {
    return (
      <main aria-label="review-queue" className="mx-auto max-w-4xl space-y-8 px-6 py-8">
        <h1 className="text-2xl font-semibold">Review queue</h1>
        <p className="text-ink-muted text-sm">You don&apos;t have reviewer access to this queue.</p>
      </main>
    );
  }

  return <ReviewQueueList />;
}

function ReviewQueueList() {
  const queue = useReviewQueue();
  const router = useRouter();

  if (queue.isLoading) return <p>Loading review queue…</p>;
  if (queue.isError) return <p role="alert">Could not load the review queue.</p>;

  const entries = queue.data ?? [];

  if (entries.length === 0) {
    return (
      <main aria-label="review-queue" className="mx-auto max-w-4xl space-y-8 px-6 py-8">
        <h1 className="text-2xl font-semibold">Review queue</h1>
        <p className="text-ink-muted text-sm">No assessments are awaiting your review.</p>
      </main>
    );
  }

  return (
    <main aria-label="review-queue" className="mx-auto max-w-4xl space-y-8 px-6 py-8">
      <h1 className="text-2xl font-semibold">Review queue</h1>
      <p className="text-ink-muted text-sm">{entries.length} assessment{entries.length !== 1 ? "s" : ""} awaiting review.</p>
      <div aria-label="review-queue-entries" role="list" className="border-hairline mt-4 overflow-hidden rounded-lg border">
        {entries.map((entry) => (
          <QueueRow
            key={entry.assessment_id}
            density="compact"
            onClick={() => router.push(`/use-cases/${entry.use_case_id}`)}
          >
            <span aria-label="queue-entry" className="flex items-center gap-2">
              <TierBadge
                value={toTierMember(entry.tier_snapshot)}
                variant="compact"
              />
              {entry.submitted_by_name && (
                <span aria-label="submitted-by" className="text-ink-muted">
                  {entry.submitted_by_name}
                </span>
              )}
            </span>
            {entry.submitted_at && (
              <time dateTime={entry.submitted_at} aria-label="submitted-at" className="text-ink-muted">
                {new Date(entry.submitted_at).toLocaleDateString()}
              </time>
            )}
          </QueueRow>
        ))}
      </div>
    </main>
  );
}
