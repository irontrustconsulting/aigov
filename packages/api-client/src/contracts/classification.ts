/**
 * One canonical Classification view, with the gate-1 and gate-2 projections
 * as `Omit<>` views. DM-S4b (WI-6b): ClassificationRead gains `status` —
 * the gate-1 projection now carries both `requires_context` and `status`.
 */
import type { ClassificationStatus, EUAIActTier } from "./enums";

export interface ClassificationCanonical {
  id: string;
  use_case_id: string;
  tier: EUAIActTier;
  rationale: string;
  version: number;
  is_current: boolean;
  overridden: boolean;
  proposed_tier: EUAIActTier | null;
  basis_subcategory_code: string | null;
  basis_legal_ref: string | null;
  requires_context: boolean;
  status: ClassificationStatus;
  created_at: string;
  updated_at: string;
}

/** app/schemas/use_cases.py ClassificationRead — carries both `requires_context`
 * and `status` (WI-6b, D-73: wizard branches on status for down-selection). */
export type ClassificationRead = Omit<ClassificationCanonical, "created_at" | "updated_at">;

/** app/schemas/classification.py ClassificationStatusRead — no `requires_context`. */
export type ClassificationStatusRead = Omit<ClassificationCanonical, "requires_context">;
