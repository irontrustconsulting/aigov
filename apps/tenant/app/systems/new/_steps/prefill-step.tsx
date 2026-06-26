"use client";

import { useState } from "react";
import { Button, PageHeader, PageScaffold, PrefillWithBasis, Skeleton, type Provenance } from "@irontrust/ui";
import type { CatalogueFactOut } from "@irontrust/api-client";
import { usePrefill } from "@/lib/intake";

/** A catalogue fact's `value` is a free-form dict — pick the single value if
 * there is exactly one key (the common case), otherwise fall back to a
 * compact JSON rendering. There is no enum/label to reconstruct here (D-21):
 * this is just a display projection of whatever the server returned. */
function factValueLabel(value: Record<string, unknown>): string {
  const entries = Object.entries(value);
  if (entries.length === 1) return String(entries[0]![1]);
  return JSON.stringify(value);
}

const NOT_APPLICABLE_OPTION = [{ value: "not_applicable", label: "Not applicable to my system" }];

export interface PrefillStepProps {
  systemId: string;
  onContinue: () => void;
}

/**
 * WI-6: confirm/amend panel over GET /systems/{id}/prefill. Per DF1-8,
 * "amend" is presentational only — the structured WI-5 fields already
 * submitted are the capture of record, so an override here updates only
 * local display state and never issues a mutation. facts == [] (custom
 * system, or no catalogue facts yet) → panel absent, never an error.
 */
export function PrefillStep({ systemId, onContinue }: PrefillStepProps) {
  const prefill = usePrefill(systemId);
  const [amended, setAmended] = useState<Record<string, string | undefined>>({});

  if (prefill.isLoading) return <Skeleton />;
  if (prefill.isError) {
    // Never block the spine on a prefill read failure — it is a display
    // aid, not a gate (UX-1: a gate surfaces only when the owner's action
    // is required).
    return (
      <PageScaffold>
        <section aria-label="prefill-confirm">
          <Button type="button" onClick={onContinue}>
            Continue
          </Button>
        </section>
      </PageScaffold>
    );
  }

  const facts = prefill.data?.facts ?? [];

  return (
    <PageScaffold>
      <section aria-label="prefill-confirm" className="space-y-4">
        <PageHeader title="Review catalogue facts" subtitle="These facts have been pre-filled from the product catalogue. Amend any that don't apply to your system." />
        {facts.length > 0 && (
          <ul className="space-y-3">
            {facts.map((fact: CatalogueFactOut) => (
              <li key={fact.key}>
                <PrefillWithBasis
                  valueLabel={amended[fact.key] ?? factValueLabel(fact.value)}
                  basis={
                    fact.source_label
                      ? `${fact.source_label}${fact.last_checked_at ? ` · checked ${fact.last_checked_at}` : ""}`
                      : "From the product catalogue"
                  }
                  provenance={fact.provenance as Provenance}
                  options={NOT_APPLICABLE_OPTION}
                  onOverride={(newValue) => {
                    const label =
                      NOT_APPLICABLE_OPTION.find((o) => o.value === newValue)?.label ?? newValue;
                    setAmended((prev) => ({ ...prev, [fact.key]: label }));
                  }}
                />
              </li>
            ))}
          </ul>
        )}
        <Button type="button" onClick={onContinue}>
          Continue
        </Button>
      </section>
    </PageScaffold>
  );
}
