import type { AtoDocumentRead } from "@irontrust/api-client";

interface Props {
  doc: AtoDocumentRead;
}

/**
 * ATO document view (DF6-5, INV-44, D-34).
 * Drift caveat is ALWAYS shown — basis_is_current_state_not_authorisation_snapshot
 * is always true; no conditional. ATO authoriser identity (authorised_by_name/
 * authorised_by_email) is durable-stamped (D-13/D-14) and reliably present —
 * no §4.5 bare-ref hedge applies here.
 */
export function AtoDocumentView({ doc }: Props) {
  const { ato, current_assessment_summary, current_classification_summary } = doc;

  return (
    <article aria-label="ato-document" className="font-serif">
      {/* Drift caveat — always shown (DF6-5 / INV-44 / D-34) */}
      <div
        role="note"
        aria-label="ato-drift-caveat"
        className="bg-surface mb-4 px-4 py-3 text-sm"
        style={{
          borderLeft: "3px solid var(--verdict-attention)",
          color: "var(--verdict-attention)",
        }}
      >
        <p className="font-medium">Important: this document reflects current state, not a snapshot.</p>
        <p>
          The referenced assessment and classification are read live and may have changed since
          authorisation. This ATO record is authoritative; the assessment and classification
          sections below may have drifted.
        </p>
      </div>

      <section aria-label="ato-details">
        <h3 className="mb-2 font-semibold">Authority to Operate</h3>
        <dl className="text-sm">
          <dt className="font-medium">EU AI Act tier at authorisation</dt>
          <dd className="text-ink-muted mb-2">{ato.tier}</dd>

          <dt className="font-medium">Authorised by</dt>
          <dd className="text-ink-muted mb-2">
            {ato.authorised_by_name ?? "—"}
            {ato.authorised_by_email && (
              <span className="text-ink-muted ml-1 text-xs">({ato.authorised_by_email})</span>
            )}
          </dd>

          <dt className="font-medium">Authorised at</dt>
          <dd className="text-ink-muted mb-2">
            {new Date(ato.authorised_at).toLocaleString()}
          </dd>

          <dt className="font-medium">Submission round</dt>
          <dd className="text-ink-muted mb-2">{ato.submission_round}</dd>

          <dt className="font-medium">Residual risk statement</dt>
          <dd className="text-ink-muted mb-2 whitespace-pre-wrap">
            {ato.residual_risk_statement}
          </dd>

          <dt className="font-medium">Current lifecycle state</dt>
          <dd className="text-ink-muted mb-2">{ato.live_state}</dd>
        </dl>
      </section>

      <section aria-label="current-assessment-summary" className="mt-4">
        <h3 className="mb-2 font-semibold">Current Assessment (live read)</h3>
        <dl className="text-sm">
          <dt className="font-medium">Status</dt>
          <dd className="text-ink-muted mb-2">{current_assessment_summary.status}</dd>
          <dt className="font-medium">Type</dt>
          <dd className="text-ink-muted mb-2">{current_assessment_summary.type}</dd>
          <dt className="font-medium">Tier snapshot</dt>
          <dd className="text-ink-muted mb-2">{current_assessment_summary.tier_snapshot}</dd>
          <dt className="font-medium">Version</dt>
          <dd className="text-ink-muted mb-2">{current_assessment_summary.version}</dd>
        </dl>
      </section>

      <section aria-label="current-classification-summary" className="mt-4">
        <h3 className="mb-2 font-semibold">Current Classification (live read)</h3>
        {current_classification_summary ? (
          <dl className="text-sm">
            <dt className="font-medium">Tier</dt>
            <dd className="text-ink-muted mb-2">{current_classification_summary.tier}</dd>
            <dt className="font-medium">Status</dt>
            <dd className="text-ink-muted mb-2">{current_classification_summary.status}</dd>
            <dt className="font-medium">Version</dt>
            <dd className="text-ink-muted mb-2">{current_classification_summary.version}</dd>
            {current_classification_summary.rationale && (
              <>
                <dt className="font-medium">Rationale</dt>
                <dd className="text-ink-muted mb-2">
                  {current_classification_summary.rationale}
                </dd>
              </>
            )}
          </dl>
        ) : (
          <p className="text-ink-muted text-sm">No classification on record.</p>
        )}
      </section>
    </article>
  );
}
