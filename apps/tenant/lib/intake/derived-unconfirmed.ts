import type { IntakeFieldBasis, IntakeFieldName, IntakePrefillBases } from "@/app/systems/new/wizard-state";

const DERIVED_FIELDS: IntakeFieldName[] = ["operatorRoleId", "lifecycleStage"];

/**
 * FE-32/INV-83 (V2, FIX-RESUME-REGATE): the set of derived intake fields
 * still requiring disposition. Shared by IntakeCaptureStep and the
 * pre-commit disposition gate so the two surfaces can't diverge.
 */
export function derivedUnconfirmed(
  prefillBases: IntakePrefillBases | null,
  confirmedIntakeFields: string[]
): IntakeFieldName[] {
  return DERIVED_FIELDS.filter((field) => {
    const basis: IntakeFieldBasis | undefined = prefillBases?.[field as keyof IntakePrefillBases];
    return basis === "derived" && !confirmedIntakeFields.includes(field);
  });
}
