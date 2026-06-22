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
    <section aria-label="sign-off-panel">
      <h2>Classification sign-off</h2>

      <dl>
        <dt>Proposed tier</dt>
        <dd>{classification.tier}</dd>

        {classification.rationale && (
          <>
            <dt>Rationale</dt>
            <dd>{classification.rationale}</dd>
          </>
        )}

        {classification.basis_subcategory_code && (
          <>
            <dt>Basis</dt>
            <dd>{classification.basis_subcategory_code}</dd>
          </>
        )}

        {classification.overridden && (
          <>
            <dt>Override</dt>
            <dd>This classification has been manually overridden.</dd>
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
      >
        {signOff.isPending ? "Signing off…" : "Sign off classification"}
      </button>
    </section>
  );
}
