"use client";

import { useState } from "react";
import { useSignOff, BadFromStateError } from "@/lib/assess";
import { BadFromStateBanner } from "@irontrust/ui";
import type { ClassificationStatusRead } from "@irontrust/api-client";

interface Props {
  useCaseId: string;
  classification: ClassificationStatusRead;
}

/**
 * Classification sign-off panel (UI-F4-ASSURE WI-3) — reviewer branch,
 * classification status = pending_review.
 * No If-Match (server route has none). 409/403 → BadFromStateBanner only.
 * On success: lifecycle refetched (eu_tier stamped); court moves forward.
 * Disambiguation: this panel shows for PENDING_REVIEW; ReviewPanel for IN_REVIEW
 * AIIA. Both map to "reviewer" court; never both panels at once (DF4-2).
 */
export function SignOffPanel({ useCaseId, classification }: Props) {
  const [blocked, setBlocked] = useState(false);
  const signOff = useSignOff(useCaseId);

  return (
    <section aria-label="sign-off-panel" className="border-hairline rounded-lg border p-4 space-y-4">
      <h2 className="text-lg font-semibold">Classification sign-off</h2>

      <dl className="space-y-2 text-sm">
        <dt className="font-medium">Proposed tier</dt>
        <dd className="text-ink-muted">{classification.tier}</dd>

        {classification.rationale && (
          <>
            <dt className="font-medium">Rationale</dt>
            <dd className="text-ink-muted">{classification.rationale}</dd>
          </>
        )}

        {classification.basis_subcategory_code && (
          <>
            <dt className="font-medium">Basis</dt>
            <dd className="text-ink-muted">{classification.basis_subcategory_code}</dd>
          </>
        )}

        {classification.overridden && (
          <>
            <dt className="font-medium">Override</dt>
            <dd className="text-ink-muted">This classification has been manually overridden.</dd>
          </>
        )}
      </dl>

      {blocked && <BadFromStateBanner />}

      <button
        onClick={() => {
          setBlocked(false);
          signOff.mutate(undefined, {
            onError: () => setBlocked(true),
          });
        }}
        disabled={signOff.isPending}
        aria-busy={signOff.isPending}
        className="rounded px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
        style={{ background: "var(--color-brand)" }}
      >
        {signOff.isPending ? "Signing off…" : "Sign off classification"}
      </button>
    </section>
  );
}
