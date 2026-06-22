"use client";

import Link from "next/link";
import { useMe, useReviewQueue } from "@/lib/assess";

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
      <main aria-label="review-queue">
        <h1>Review queue</h1>
        <p>You don&apos;t have reviewer access to this queue.</p>
      </main>
    );
  }

  return <ReviewQueueList />;
}

function ReviewQueueList() {
  const queue = useReviewQueue();

  if (queue.isLoading) return <p>Loading review queue…</p>;
  if (queue.isError) return <p role="alert">Could not load the review queue.</p>;

  const entries = queue.data ?? [];

  if (entries.length === 0) {
    return (
      <main aria-label="review-queue">
        <h1>Review queue</h1>
        <p>No assessments are awaiting your review.</p>
      </main>
    );
  }

  return (
    <main aria-label="review-queue">
      <h1>Review queue</h1>
      <p>{entries.length} assessment{entries.length !== 1 ? "s" : ""} awaiting review.</p>
      <ol aria-label="review-queue-entries">
        {entries.map((entry) => (
          <li key={entry.assessment_id} aria-label="queue-entry">
            <Link href={`/use-cases/${entry.use_case_id}`} aria-label={`Review use case`}>
              <span aria-label="tier">{entry.tier_snapshot}</span>
            </Link>
            {entry.submitted_by_name && (
              <span aria-label="submitted-by">Submitted by {entry.submitted_by_name}</span>
            )}
            {entry.submitted_at && (
              <time dateTime={entry.submitted_at} aria-label="submitted-at">
                {new Date(entry.submitted_at).toLocaleDateString()}
              </time>
            )}
          </li>
        ))}
      </ol>
    </main>
  );
}
