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
  use_case_purpose: string | null;
  context_blob: Record<string, unknown>;
  usage_context_id: string | null;
  human_oversight_type_id: string | null;
  data_category_ids: string[];
  affected_party_ids: string[];
}

/** Response from POST /v1/registrations — full system + use case + classification,
 * no post-create refetch needed (A2). */
export interface RegistrationRead {
  system: SystemDetail;
  use_case: UseCaseRead;
  classification: ClassificationRead;
}
