"use client";

import { useState } from "react";
import { Button } from "../primitives/button";
import { ProvenanceBadge, type Provenance } from "./provenance-badge";

export interface StructuredOption {
  value: string;
  label: string;
}

export interface PrefillWithBasisProps {
  /** The current value's display label — server-derived. */
  valueLabel: string;
  /** The shown basis for the current value — server-derived. */
  basis: string;
  /** Server-derived provenance (PAT-8, INV-13) — never client-set. */
  provenance: Provenance;
  /** The override is itself a structured pick (FE-4), never free text. */
  options: StructuredOption[];
  /** The client never authors a `provenance` value — this callback's payload
   * carries only the chosen value and an optional justification. The
   * deviation is tracked server-side from this call, not from a
   * client-supplied provenance. */
  onOverride: (newValue: string, justification?: string) => void;
}

/**
 * FE-5: the §1.5 spine at field level. Renders the server-derived
 * provenance badge, the shown basis, and a one-click override whose input
 * is also a structured pick plus optional justification.
 */
export function PrefillWithBasis({
  valueLabel,
  basis,
  provenance,
  options,
  onOverride,
}: PrefillWithBasisProps) {
  const [overriding, setOverriding] = useState(false);
  const [selected, setSelected] = useState(options[0]?.value ?? "");
  const [justification, setJustification] = useState("");

  return (
    <div className="space-y-2 rounded border border-hairline bg-surface p-4">
      <div className="flex items-center gap-2">
        <span className="text-sm font-medium text-ink">{valueLabel}</span>
        <ProvenanceBadge provenance={provenance} />
      </div>
      <p className="text-xs text-ink-muted">{basis}</p>

      {!overriding && (
        <Button variant="ghost" type="button" onClick={() => setOverriding(true)}>
          Override
        </Button>
      )}

      {overriding && (
        <div className="space-y-3 border-t border-hairline pt-3">
          <div className="space-y-1">
            <label htmlFor="prefill-override-select" className="block text-sm font-medium text-ink">
              New value
            </label>
            <select
              id="prefill-override-select"
              value={selected}
              onChange={(e) => setSelected(e.target.value)}
              className="block w-full rounded border border-hairline bg-surface px-3 py-1.5 text-sm text-ink focus:outline-none focus:ring-1 focus:ring-ink/20"
            >
              {options.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>

          <div className="space-y-1">
            <label htmlFor="prefill-override-justification" className="block text-sm font-medium text-ink-muted">
              Justification (optional)
            </label>
            <textarea
              id="prefill-override-justification"
              rows={2}
              value={justification}
              onChange={(e) => setJustification(e.target.value)}
              className="block w-full rounded border border-hairline bg-surface px-3 py-1.5 text-sm text-ink-muted focus:outline-none focus:ring-1 focus:ring-ink/20"
            />
          </div>

          <div className="flex gap-2">
            <Button
              type="button"
              onClick={() => {
                onOverride(selected, justification || undefined);
                setOverriding(false);
                setJustification("");
              }}
            >
              Confirm override
            </Button>
            <Button variant="secondary" type="button" onClick={() => setOverriding(false)}>
              Cancel
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
