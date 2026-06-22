"use client";

import { useState } from "react";
import { useRecordReview, StaleLockError, BadFromStateError } from "@/lib/assess";
import { StaleLockBanner, BadFromStateBanner } from "@irontrust/ui";
import type { ReviewDecision } from "@irontrust/api-client";

interface Props {
  useCaseId: string;
  assessmentId: string;
  assessmentLockVersion: number;
}

/**
 * AIIA review controls for the reviewer branch (UI-F4-ASSURE WI-2).
 * Sends If-Match (FE-6): 412 → StaleLockBanner; 409 → BadFromStateBanner.
 * note is required when decision = "changes_requested" (server-enforced 422;
 * also client-side disabled until non-empty).
 * act-SoD enforcement is at the server (INV-28, assert_distinct_workflow_actor);
 * a 403 surfaces as a blocked reason via BadFromStateBanner.
 */
export function ReviewPanel({ useCaseId, assessmentId, assessmentLockVersion }: Props) {
  const [decision, setDecision] = useState<ReviewDecision | null>(null);
  const [note, setNote] = useState("");
  const [error, setError] = useState<"stale" | "bad_state" | null>(null);
  const review = useRecordReview(useCaseId, assessmentId);

  const requiresNote = decision === "changes_requested";
  const canSubmit = decision !== null && (!requiresNote || note.trim().length > 0);

  function handleSubmit() {
    if (!decision) return;
    setError(null);
    review.mutate(
      {
        body: { decision, note: note.trim() || null },
        lockVersion: assessmentLockVersion,
      },
      {
        onError: (err) => {
          if (err instanceof StaleLockError) setError("stale");
          else setError("bad_state");
        },
      }
    );
  }

  return (
    <section aria-label="review-panel">
      <h2>Review assessment</h2>

      {error === "stale" && <StaleLockBanner onReload={() => setError(null)} />}
      {error === "bad_state" && <BadFromStateBanner />}

      <fieldset>
        <legend>Decision</legend>

        <label>
          <input
            type="radio"
            name="review-decision"
            value="approved"
            checked={decision === "approved"}
            onChange={() => setDecision("approved")}
          />
          Approve
        </label>

        <label>
          <input
            type="radio"
            name="review-decision"
            value="changes_requested"
            checked={decision === "changes_requested"}
            onChange={() => setDecision("changes_requested")}
          />
          Request changes
        </label>
      </fieldset>

      {requiresNote && (
        <label>
          <span>Note (required when requesting changes)</span>
          <textarea
            value={note}
            onChange={(e) => setNote(e.target.value)}
            rows={4}
            aria-required="true"
          />
        </label>
      )}

      <button
        onClick={handleSubmit}
        disabled={!canSubmit || review.isPending}
        aria-busy={review.isPending}
      >
        {review.isPending ? "Submitting…" : "Submit review"}
      </button>
    </section>
  );
}
