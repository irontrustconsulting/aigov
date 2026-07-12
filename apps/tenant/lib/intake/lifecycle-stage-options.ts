import type { SelectOption } from "@irontrust/ui";

/** Shared between IntakeCaptureStep and the pre-commit disposition gate
 * (V2/N2, FIX-RESUME-REGATE) — not server vocab, a fixed client enum. */
export const LIFECYCLE_STAGE_OPTIONS: SelectOption[] = [
  { value: "development", label: "Development" },
  { value: "pilot", label: "Pilot" },
  { value: "production", label: "Production" },
  { value: "retired", label: "Retired" },
];
