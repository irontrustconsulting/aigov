/** app/schemas/system.py — SystemCreate/SystemRead/SystemDetail/PrefillResponse. */
import type { ProvenanceConfidence, SystemLifecycleStage } from "./enums";
import type { CatalogueVendorRef, VocabItemOut } from "./reference";

export interface CatalogueProductRef {
  id: string;
  name: string;
}

/** GET /v1/systems — lean list-view (app/schemas/system.py SystemRead), no
 * vocab labels or use-case data. UI-F2-PORTFOLIO's A2 zero-use-case merge:
 * a system here with no matching entry in the GET /portfolio result has no
 * use cases yet. */
export interface SystemRead {
  id: string;
  tenant_id: string;
  name: string;
  is_custom: boolean;
  lifecycle_stage: SystemLifecycleStage | null;
  created_at: string;
  updated_at: string;
}

/** The request body for POST /v1/systems. `is_custom` XOR a catalogue link
 * (`catalogue_product_id`) is a server guard (422) the client mirrors
 * structurally in WI-5 — never sends `catalogue_vendor_id` itself, the
 * server derives it from the product.
 * Use-distinguishing context (usage_context, human_oversight, data categories,
 * affected parties) lives on the use case as of DM-S1 — see UseCaseCreate. */
export interface SystemCreate {
  name: string;
  is_custom: boolean;
  catalogue_product_id: string | null;
  catalogue_vendor_id: string | null;
  owner_user_id: string | null;
  operator_role_id: string | null;
  hosting_model_id: string | null;
  lifecycle_stage: SystemLifecycleStage | null;
  purpose: string | null;
}

export interface UseCaseStateSummary {
  use_case_id: string;
  state: string;
}

export interface SystemDetail {
  id: string;
  name: string;
  is_custom: boolean;
  catalogue_product: CatalogueProductRef | null;
  catalogue_vendor: CatalogueVendorRef | null;
  owner_user_id: string | null;
  operator_role: VocabItemOut | null;
  hosting_model: VocabItemOut | null;
  lifecycle_stage: SystemLifecycleStage | null;
  purpose: string | null;
  use_case_count: number;
  use_case_lifecycle_states: UseCaseStateSummary[];
  created_at: string;
  updated_at: string;
}

export interface CatalogueFactOut {
  key: string;
  value: Record<string, unknown>;
  source_url: string | null;
  source_label: string | null;
  last_checked_at: string | null;
  provenance: ProvenanceConfidence;
}

export interface PrefillResponse {
  catalogue_product_id: string | null;
  facts: CatalogueFactOut[];
}
