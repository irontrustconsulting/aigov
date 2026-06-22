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
      <h3>Review history</h3>
      <ol>
        {detail.data.reviews.map((r) => (
          <li key={r.id}>
            <span aria-label="reviewer">
              {r.reviewer_display_name ?? "Reviewer"}
            </span>
            {" — "}
            <span aria-label="decision">
              {r.decision === "approved" ? "Approved" : "Requested changes"}
            </span>
            {" · "}
            <span aria-label="submission-round">Round {r.submission_round}</span>
            {" · "}
            <time dateTime={r.created_at}>
              {new Date(r.created_at).toLocaleDateString()}
            </time>
            {r.note && (
              <blockquote aria-label="review-note">{r.note}</blockquote>
            )}
          </li>
        ))}
      </ol>
    </section>
  );
}
