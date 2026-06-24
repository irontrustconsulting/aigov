"use client";

import { useState } from "react";
import { useAuthorise, BadFromStateError } from "@/lib/assess";
import { BadFromStateBanner } from "@irontrust/ui";

interface Props {
  useCaseId: string;
}

/**
 * Authorise panel (UI-F4-ASSURE WI-4) — authoriser branch,
 * lifecycle state = pending_authorisation.
 * No If-Match (route has none). 409/403 → BadFromStateBanner only; no 412 path.
 * residual_risk_statement required client-side (button disabled until non-empty).
 * act-SoD (authoriser ∉ {reviewer, submitter}) enforced at server (INV-28).
 * On success: ATO terminal renders via invalidated useAuthorisation query (INV-32).
 */
export function AuthorisePanel({ useCaseId }: Props) {
  const [residualRisk, setResidualRisk] = useState("");
  const [blocked, setBlocked] = useState(false);
  const authorise = useAuthorise(useCaseId);

  const canSubmit = residualRisk.trim().length > 0;

  return (
    <section aria-label="authorise-panel" className="border-hairline rounded-lg border p-4 space-y-4">
      <h2 className="text-lg font-semibold">Grant deployment authorisation</h2>
      <p className="text-ink-muted text-sm">
        Review the assembled AIIA and approved classification above. Record the residual
        risk statement before granting the Authority to Operate (ATO).
      </p>

      {blocked && <BadFromStateBanner />}

      <label className="block space-y-1">
        <span className="text-sm font-medium">Residual risk statement</span>
        <textarea
          value={residualRisk}
          onChange={(e) => setResidualRisk(e.target.value)}
          rows={4}
          aria-required="true"
          placeholder="Describe residual risks accepted under this authorisation…"
          className="border-hairline w-full rounded border px-3 py-2 text-sm"
        />
      </label>

      <button
        onClick={() => {
          setBlocked(false);
          authorise.mutate(
            { residual_risk_statement: residualRisk.trim() },
            { onError: () => setBlocked(true) }
          );
        }}
        disabled={!canSubmit || authorise.isPending}
        aria-busy={authorise.isPending}
        className="rounded px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
        style={{ background: "var(--color-brand)" }}
      >
        {authorise.isPending ? "Authorising…" : "Grant authorisation"}
      </button>
    </section>
  );
}
