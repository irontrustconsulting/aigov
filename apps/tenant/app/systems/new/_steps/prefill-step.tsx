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
  catalogueProductId: string | null;
  /** WI-6: called with fact dispositions so the wizard can record them for
   * submission. Confirmed = fact accepted as-is; amended = fact overridden. */
  onContinue: (confirmedKeys: string[], amendedKeys: string[]) => void;
}

/**
 * WI-8 (DM-S2): confirm/amend panel over GET /catalogue/products/{id}/prefill.
 * Re-keyed to catalogueProductId so the step works before a system exists
 * (DF-D2-2). Per DF1-8, "amend" is presentational only — structured intake
 * fields are the capture of record. facts == [] (custom / no product) →
 * panel absent, never an error.
 */
export function PrefillStep({ catalogueProductId, onContinue }: PrefillStepProps) {
  const prefill = usePrefill(catalogueProductId);
  const [amended, setAmended] = useState<Record<string, string | undefined>>({});

  if (prefill.isLoading) return <Skeleton />;
  if (prefill.isError) {
    // Never block the spine on a prefill read failure — it is a display
    // aid, not a gate (UX-1: a gate surfaces only when the owner's action
    // is required).
    return (
      <PageScaffold>
        <section aria-label="prefill-confirm">
          <Button type="button" onClick={() => onContinue([], [])}>
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
        <Button
          type="button"
          onClick={() => {
            // WI-6: all non-amended facts are confirmed as-is on Continue (INV-83).
            const amendedKeys = Object.keys(amended);
            const confirmedKeys = facts
              .map((f: CatalogueFactOut) => f.key)
              .filter((k: string) => !amendedKeys.includes(k));
            onContinue(confirmedKeys, amendedKeys);
          }}
        >
          Continue
        </Button>
      </section>
    </PageScaffold>
  );
}
