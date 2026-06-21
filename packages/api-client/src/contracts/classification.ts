/**
 * One canonical Classification view, with the gate-1 (`requires_context`,
 * use_cases.py ClassificationRead) and gate-2 (`status`, classification.py
 * ClassificationStatusRead) projections derived from it as `Omit<>` views —
 * per the sprint doc's instruction not to hand-duplicate the two shapes.
 * The canonical type is a superset; each projection narrows to exactly the
 * fields the real backend response carries, no more, no less.
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
  /** gate-1 only (use_cases.py ClassificationRead). */
  requires_context: boolean;
  /** gate-2 only (classification.py ClassificationStatusRead). */
  status: ClassificationStatus;
  created_at: string;
  updated_at: string;
}

/** app/schemas/use_cases.py ClassificationRead — no `status`. */
export type ClassificationRead = Omit<ClassificationCanonical, "status" | "created_at" | "updated_at">;

/** app/schemas/classification.py ClassificationStatusRead — no `requires_context`. */
export type ClassificationStatusRead = Omit<ClassificationCanonical, "requires_context">;
