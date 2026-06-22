/**
 * UI-F5-EVIDENCE contract types — mirrors app/schemas/evidence.py and the
 * evidence_links manifest field added to AssessmentItemRead (WI-F).
 */

export interface EvidenceRead {
  id: string;
  title: string;
  content_type: string | null;
  size_bytes: number | null;
  sha256: string | null;
  /** Bare UUID — no name display in MVP (DF5-11). */
  uploaded_by_user_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface EvidenceListItem extends EvidenceRead {
  link_count: number;
}

export interface EvidenceListResponse {
  items: EvidenceListItem[];
  next_cursor: string | null;
}

/** GET /v1/evidence/{id} — fetched only on explicit download intent (DF5-3). */
export interface EvidenceDetailRead extends EvidenceRead {
  /** Short-TTL presigned S3 URL. Navigate browser to this; never inline-render. */
  download_url: string;
}

/** POST /v1/assessments/{aid}/items/{iid}/evidence-links body. No If-Match (DF5-4). */
export interface EvidenceLinkCreate {
  evidence_id: string;
}

/** POST /v1/assessments/{aid}/items/{iid}/evidence-links response (ids-only). */
export interface EvidenceLinkRead {
  id: string;
  item_id: string;
  evidence_id: string;
}

/**
 * Self-describing manifest entry on AssessmentItemRead.evidence_links (WI-F / DF5-8).
 * No download_url — rendering triggers no evidence.access (DF5-3).
 * Batch-loaded in assemble_aiia_items; the repository surface is not needed to
 * display the per-item manifest.
 */
export interface ItemEvidenceRead {
  evidence_id: string;
  title: string;
  sha256: string | null;
  content_type: string | null;
  size_bytes: number | null;
}
