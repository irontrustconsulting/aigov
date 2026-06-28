/** Draft-registration contracts (DM-S3, D-66). */

export interface DraftRegistrationRead {
  id: string;
  tenant_id: string;
  owner_user_id: string;
  draft_blob: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface DraftRegistrationPatch {
  draft_blob: Record<string, unknown>;
}
