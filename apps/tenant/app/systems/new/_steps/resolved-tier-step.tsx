"use client";

import { useState, type FormEvent } from "react";
import { Button, FreeText, SingleSelect, SodAction, TierBadge, toTierMember, type SelectOption } from "@irontrust/ui";
import type { ClassificationRead, EUAIActTier } from "@irontrust/api-client";
import { useEUSubcategories, useMe, useOverrideClassification } from "@/lib/intake";

const TIER_OPTIONS: SelectOption[] = [
  { value: "high_risk", label: "High risk" },
  { value: "limited_risk", label: "Limited risk" },
  { value: "minimal_risk", label: "Minimal risk" },
];

export interface ResolvedTierStepProps {
  useCaseId: string;
  classification: ClassificationRead;
  onOverrideApplied: (classification: ClassificationRead) => void;
  onContinue: () => void;
}

/**
 * WI-7 (resolved branch): tier + basis reasoning-first (UX-4), and the
 * gate-1 override ladder. `tier`/`subcategory_code` are structured picks
 * (FE-4) — the subcategory list is filtered to the chosen tier so a
 * mismatched pick is unreachable client-side (the server still 422s on a
 * mismatch; this is prevention, not a substitute for it).
 *
 * The override control is wrapped in SodAction, barred for anyone who
 * isn't system_owner (FE-8) — structural, not a transient block.
 * TierBadge card variant: tier hero, basis, override ladder (INV-64).
 */
export function ResolvedTierStep({
  useCaseId,
  classification,
  onOverrideApplied,
  onContinue,
}: ResolvedTierStepProps) {
  const me = useMe();
  const subcategories = useEUSubcategories();
  const overrideMutation = useOverrideClassification(useCaseId);

  const [overriding, setOverriding] = useState(false);
  const [tier, setTier] = useState<EUAIActTier>(
    classification.tier === "prohibited" ? "high_risk" : classification.tier
  );
  const [subcategoryCode, setSubcategoryCode] = useState("");
  const [justification, setJustification] = useState("");

  const isSystemOwner = me.data?.governance_roles.some((r) => r.key === "system_owner") ?? false;
  const subcategoryOptions: SelectOption[] = (subcategories.data ?? [])
    .filter((s) => s.tier === tier)
    .map((s) => ({ value: s.code, label: s.name }));

  function submitOverride(e: FormEvent) {
    e.preventDefault();
    overrideMutation.mutate(
      { tier, subcategory_code: subcategoryCode, justification: justification || null },
      { onSuccess: (data) => onOverrideApplied(data.classification) }
    );
  }

  const tierBasis = (
    <>
      {classification.rationale && <p>{classification.rationale}</p>}
      {classification.basis_subcategory_code && (
        <p>Subcategory: {classification.basis_subcategory_code}</p>
      )}
      {classification.basis_legal_ref && (
        <p>Legal basis: {classification.basis_legal_ref}</p>
      )}
    </>
  );

  const overrideForm = !overriding ? (
    <Button type="button" variant="secondary" onClick={() => setOverriding(true)}>
      Override classification
    </Button>
  ) : (
    <form aria-label="override-form" onSubmit={submitOverride}>
      <SingleSelect
        id="override-tier"
        label="Tier"
        value={tier}
        options={TIER_OPTIONS}
        onChange={(v) => {
          setTier(v as EUAIActTier);
          setSubcategoryCode("");
        }}
      />
      <SingleSelect
        id="override-subcategory"
        label="Subcategory"
        value={subcategoryCode}
        options={subcategoryOptions}
        onChange={setSubcategoryCode}
      />
      <FreeText
        id="override-justification"
        label="Justification (optional)"
        value={justification}
        onChange={setJustification}
      />
      {overrideMutation.isError && (
        <p role="alert">Could not apply the override. Check the tier/subcategory pair and try again.</p>
      )}
      <Button type="submit" disabled={!subcategoryCode || overrideMutation.isPending}>
        Confirm override
      </Button>
    </form>
  );

  return (
    <section aria-label="resolved-tier" className="mx-auto max-w-4xl space-y-4 px-6 py-8">
      <h2 className="text-lg font-semibold">Classification result</h2>
      <TierBadge
        value={toTierMember(classification.tier)}
        variant="card"
        basis={tierBasis}
        overrideLadder={
          <SodAction barred={!isSystemOwner}>{overrideForm}</SodAction>
        }
      />

      <Button type="button" onClick={onContinue}>
        Continue
      </Button>
    </section>
  );
}
