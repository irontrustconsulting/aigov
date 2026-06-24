"use client";

import { useAuthorisation } from "@/lib/assess";

interface Props {
  useCaseId: string;
}

/**
 * ATO terminal (UI-F4-ASSURE WI-5) — shown to any gov role when the use case
 * is in the "authorised" lifecycle state.
 * live_state is read from the GET /authorisation response (INV-32) — never
 * inferred from row existence. authorised_by_name from INV-34 join.
 * Drift caveat: rendered when live_state ≠ "authorised" (DF4-4 / INV-44 precedent).
 * 404: use case has never been authorised → renders nothing.
 */
export function AtoTerminal({ useCaseId }: Props) {
  const query = useAuthorisation(useCaseId);

  if (query.isLoading) return null;

  // 404 = never authorised; any other error = transient — render nothing
  if (query.isError || !query.data) return null;

  const ato = query.data;
  const isDrifted = ato.live_state !== "authorised";

  return (
    <section aria-label="ato-terminal" className="border-hairline rounded-lg border p-4 space-y-4">
      <h2 className="text-lg font-semibold">Authority to Operate</h2>

      {isDrifted && (
        <p role="alert" aria-label="ato-drift-caveat" className="text-sm">
          Note: the deployment status has changed since this ATO was issued
          (current state: <strong>{ato.live_state}</strong>). Review the
          current lifecycle status before relying on this record.
        </p>
      )}

      <dl className="space-y-2 text-sm">
        <dt className="font-medium">Tier</dt>
        <dd className="text-ink-muted">{ato.tier}</dd>

        <dt className="font-medium">Authorised by</dt>
        <dd className="text-ink-muted">{ato.authorised_by_name ?? "Unknown"}</dd>

        <dt className="font-medium">Authorised at</dt>
        <dd className="text-ink-muted">{new Date(ato.authorised_at).toLocaleString()}</dd>

        <dt className="font-medium">Residual risk</dt>
        <dd className="text-ink-muted">{ato.residual_risk_statement}</dd>

        <dt className="font-medium">Assessment version</dt>
        <dd className="text-ink-muted">{ato.assessment_version}</dd>

        <dt className="font-medium">Submission round</dt>
        <dd className="text-ink-muted">{ato.submission_round}</dd>
      </dl>
    </section>
  );
}
