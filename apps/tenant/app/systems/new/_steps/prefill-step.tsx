"use client";

import { useState } from "react";
import { Button, PageHeader, PageScaffold, PrefillWithBasis, Skeleton, type Provenance } from "@irontrust/ui";
import type { CatalogueFactOut } from "@irontrust/api-client";
import { usePrefill, FactValue, labelForFactKey, composeBasis } from "@/lib/intake";

const NOT_APPLICABLE_OPTION = [{ value: "not_applicable", label: "Not applicable to my system" }];

export interface PrefillStepProps {
  catalogueProductId: string | null;
  /** Called with fact dispositions so the wizard can record them at submission.
   * Confirmed = fact accepted as-is; amended = fact overridden (INV-83). */
  onContinue: (confirmedKeys: string[], amendedKeys: string[]) => void;
}

/**
 * WI-8 (DM-S2): confirm/amend panel over GET /catalogue/products/{id}/prefill.
 * Re-keyed to catalogueProductId so the step works before a system exists
 * (DF-D2-2). Per DF1-8 (clarified by CAT-4), "amend" is presentational only
 * — the disposition is recorded at POST /v1/registrations (INV-83).
 * facts == [] (custom / no product) → panel absent, never an error.
 */
export function PrefillStep({ catalogueProductId, onContinue }: PrefillStepProps) {
  const prefill = usePrefill(catalogueProductId);
  const [amended, setAmended] = useState<Record<string, string | undefined>>({});

  if (prefill.isLoading) return <Skeleton />;
  if (prefill.isError) {
    // Never block the spine on a prefill read failure — it is a display
    // aid, not a gate (UX-1).
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
        <PageHeader
          title="Review catalogue facts"
          subtitle="These facts have been pre-filled from the product catalogue. Amend any that don't apply to your system."
        />
        {facts.length > 0 && (
          <ul className="space-y-3">
            {facts.map((fact: CatalogueFactOut) => {
              const isAmended = amended[fact.key] !== undefined;
              return (
                <li key={fact.key}>
                  <PrefillWithBasis
                    label={labelForFactKey(fact.key)}
                    valueLabel={amended[fact.key] ?? ""}
                    valueContent={
                      // R8: amended branch shows override label as plain valueLabel;
                      // unamended branch shows shape-typed node.
                      isAmended ? undefined : <FactValue value={fact.value} />
                    }
                    basis={composeBasis(fact)}
                    provenance={fact.provenance as Provenance}
                    options={NOT_APPLICABLE_OPTION}
                    onOverride={(newValue) => {
                      const label =
                        NOT_APPLICABLE_OPTION.find((o) => o.value === newValue)?.label ?? newValue;
                      setAmended((prev) => ({ ...prev, [fact.key]: label }));
                    }}
                  />
                </li>
              );
            })}
          </ul>
        )}
        <div className="flex items-center gap-4">
          <Button
            type="button"
            onClick={() => {
              // WI-6 (CAT-4): all non-amended facts are confirmed as-is on Continue (INV-83).
              const amendedKeys = Object.keys(amended);
              const confirmedKeys = facts
                .map((f: CatalogueFactOut) => f.key)
                .filter((k: string) => !amendedKeys.includes(k));
              onContinue(confirmedKeys, amendedKeys);
            }}
          >
            Continue
          </Button>
          {facts.length > 0 && (
            <p className="text-sm text-ink-muted">
              Facts you don&apos;t amend are recorded as confirmed when you continue.
            </p>
          )}
        </div>
      </section>
    </PageScaffold>
  );
}
