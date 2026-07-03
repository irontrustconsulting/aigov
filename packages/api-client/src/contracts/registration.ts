/** app/schemas/registration.py — RegistrationCreate / RegistrationRead (DM-S2, D-65). */
import type { SystemLifecycleStage } from "./enums";
import type { SystemDetail } from "./system";
import type { UseCaseRead } from "./use-case";
import type { ClassificationRead } from "./classification";

/** POST /v1/registrations — system-stable + first use-case facts in one body. */
export interface RegistrationCreate {
  // system-stable
  name: string;
  is_custom: boolean;
  catalogue_product_id: string | null;
  operator_role_id: string | null;
  hosting_model_id: string | null;
  lifecycle_stage: SystemLifecycleStage | null;
  owner_user_id: string | null;
  purpose: string | null;
  // first use case
  title: string;
  intended_use_category_id: string | null;
  context_blob: Record<string, unknown>;
  usage_context_id: string | null;
  human_oversight_type_id: string | null;
  data_category_ids: string[];
  affected_party_ids: string[];
  /** When present, the draft is deleted in the same transaction (D-66/SV-3). */
  draft_id?: string | null;
  /** Transient disposition signal (D-74, INV-83). Bare intake keys (e.g.
   * "operator_role_id") for explicitly confirmed derived fields; "fact:<key>"
   * for confirmed catalogue facts. Not persisted in draft_blob (B1). */
  confirmed_fields?: string[];
}

/** Response from POST /v1/registrations — full system + use case + classification,
 * no post-create refetch needed (A2). */
export interface RegistrationRead {
  system: SystemDetail;
  use_case: UseCaseRead;
  classification: ClassificationRead;
}
