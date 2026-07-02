/** app/schemas/system.py — SystemRead/SystemDetail/PrefillResponse. */
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

export interface FieldPrefill {
  value: string;
  basis: "catalogue" | "derived";
}

export interface FieldPrefills {
  hosting_model_id?: FieldPrefill;
  operator_role_id?: FieldPrefill;
  lifecycle_stage?: FieldPrefill;
  purpose?: FieldPrefill;
}

export interface PrefillResponse {
  catalogue_product_id: string | null;
  facts: CatalogueFactOut[];
  field_prefills?: FieldPrefills | null;
}
