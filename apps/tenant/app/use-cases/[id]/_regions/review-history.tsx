"use client";

import { useAssessmentDetail } from "@/lib/assess";

interface Props {
  assessmentId: string;
}

/**
 * Review history (UI-F4-ASSURE WI-7) — attributed request-changes display.
 * Sourced from AssessmentDetail.reviews (WI-9b additive field).
 * reviewer_display_name from the INV-34 membership join — never a durable
 * name/email stamp on the AssessmentReview row itself (D-25).
 * Renders nothing when reviews is empty or the detail hasn't loaded.
 * Visible to system_owner, reviewer, authoriser (not auditor, not admin —
 * caller enforces this via conditional render in assessment-page-client.tsx).
 */
export function ReviewHistory({ assessmentId }: Props) {
  const detail = useAssessmentDetail(assessmentId);

  if (!detail.data || detail.data.reviews.length === 0) return null;

  return (
    <section aria-label="review-history">
      <h3 className="font-semibold mb-2">Review history</h3>
      <ol className="space-y-3">
        {detail.data.reviews.map((r) => (
          <li key={r.id} className="border-hairline rounded-lg border p-4 text-sm">
            <div className="flex flex-wrap items-center gap-2 text-sm">
              <span aria-label="reviewer" className="font-medium">
                {r.reviewer_display_name ?? "Reviewer"}
              </span>
              <span aria-label="decision" className="text-ink-muted">
                {r.decision === "approved" ? "Approved" : "Requested changes"}
              </span>
              <span aria-label="submission-round" className="text-ink-muted">Round {r.submission_round}</span>
              <time dateTime={r.created_at} className="text-ink-muted">
                {new Date(r.created_at).toLocaleDateString()}
              </time>
            </div>
            {r.note && (
              <blockquote aria-label="review-note" className="text-ink-muted mt-2 border-l-2 pl-3 text-sm">{r.note}</blockquote>
            )}
          </li>
        ))}
      </ol>
    </section>
  );
}
