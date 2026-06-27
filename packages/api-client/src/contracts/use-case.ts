/** app/schemas/use_cases.py — UseCaseCreate/UseCaseRead/UseCaseWithClassification/OverrideRequest. */
import type { ClassificationRead } from "./classification";
import type { EUAIActTier, LifecycleState } from "./enums";
import type { AffectedPartyOut, DataCategoryOut, VocabItemOut } from "./reference";

export interface UseCaseCreate {
  system_id: string;
  title: string;
  purpose: string | null;
  context_blob: Record<string, unknown>;
  /** Use-distinguishing context (D-63/INV-76) — relocated from system in DM-S1. */
  usage_context_id: string | null;
  human_oversight_type_id: string | null;
  data_category_ids: string[];
  affected_party_ids: string[];
}

export interface UseCaseRead {
  id: string;
  tenant_id: string;
  system_id: string;
  title: string;
  purpose: string | null;
  state: LifecycleState;
  /** Unratified on the context path (C-2/V-2) — tier/basis display reads
   * the Classification snapshot, never this field. */
  eu_tier: EUAIActTier;
  /** Use-distinguishing context (resolved on read; D-63/INV-76). */
  usage_context: VocabItemOut | null;
  human_oversight_type: VocabItemOut | null;
  data_categories: DataCategoryOut[];
  affected_parties: AffectedPartyOut[];
}

export interface UseCaseWithClassification {
  use_case: UseCaseRead;
  classification: ClassificationRead;
}

/** POST .../classify/override (gate-1, system_owner-only). `tier` and
 * `subcategory_code` are structured picks (FE-4) — the client prevents the
 * server's tier/subcategory-mismatch 422 by filtering the subcategory
 * options to the chosen tier before submit, never by allowing free entry. */
export interface OverrideRequest {
  tier: EUAIActTier;
  subcategory_code: string;
  justification: string | null;
}
