/** Export / audit pack — mirrors app/schemas/export.py (Sprint 7b). Response-only. */

import type { AssessmentRead } from "./assessment";
import type { DeploymentAuthorisationRead } from "./assessment";
import type { SystemDetail } from "./system";
import type { CoverageMatrixRead } from "./coverage";

// ---------------------------------------------------------------------------
// Shared
// ---------------------------------------------------------------------------

/** Nullable actor projection — user_id/name/email all nullable (background-
 * triggered rows, future anonymisation). Render name/email when present;
 * bare user_id when null; never fabricate a name (D-25, §4.5). */
export interface ActorRef {
  user_id: string | null;
  name: string | null;
  email: string | null;
}

export interface ClassificationHistoryEntryRead {
  tier: string;
  proposed_tier: string | null;
  overridden: boolean;
  rationale: string;
  basis_subcategory_code: string | null;
  basis_legal_ref: string | null;
  status: string;
  version: number;
  signed_off_by: ActorRef | null;
}

/** By reference only — never bytes, never an embedded presigned URL (INV-40).
 * Retrieval stays on the hardened GET /v1/evidence/{id}. */
export interface EvidenceManifestEntryRead {
  id: string;
  sha256: string | null;
  title: string;
  content_type: string | null;
  size_bytes: number | null;
  back_refs: string[];
}

export interface LifecycleTrailEntryRead {
  from_state: string | null;
  to_state: string;
  occurred_at: string;
  actor: ActorRef | null;
  reason: string | null;
  triggered_by: string | null;
}

export interface AuditTrailEntryRead {
  action: string;
  occurred_at: string;
  actor: ActorRef | null;
  entity_type: string;
  entity_id: string | null;
  detail: Record<string, unknown>;
}

// ---------------------------------------------------------------------------
// Assessment section within export (INV-41 — not assemble_aiia_items)
// ---------------------------------------------------------------------------

/** Export view of an assessment item — extends AssessmentItemRead with
 * surfaces_into (the AIIA section_key this feeder item maps into, or null). */
export interface ExportAssessmentItemRead {
  id: string;
  assessment_id: string;
  section_key: string | null;
  risk_id: string | null;
  prompt: string | null;
  response: string | null;
  likelihood: number | null;
  severity: number | null;
  residual_likelihood: number | null;
  residual_severity: number | null;
  mitigation_plan: string | null;
  treatment_decision: string | null;
  treatment_rationale: string | null;
  provenance: string;
  selection_basis: string | null;
  source_ref: string | null;
  lock_version: number;
  created_at: string;
  updated_at: string;
  source_assessment_id: string | null;
  source_type: string | null;
  control_links: unknown[];
  evidence_links: unknown[];
  surfaces_into: string | null;
}

export interface FeederExportRead {
  assessment_id: string;
  type: string;
  status: string;
  items: ExportAssessmentItemRead[];
}

export interface AssessmentExportRead {
  aiia_id: string | null;
  status: string | null;
  native_items: ExportAssessmentItemRead[];
  feeders: FeederExportRead[];
}

// ---------------------------------------------------------------------------
// Use-case export
// ---------------------------------------------------------------------------

/** Reusable use-case-record body (§4.2 items 1-7); audit trail excluded here
 * (the system pack computes one combined closure across all its use cases). */
export interface UseCaseExportSectionsRead {
  use_case_id: string;
  system: SystemDetail;
  classification_history: ClassificationHistoryEntryRead[];
  assessment: AssessmentExportRead;
  evidence_manifest: EvidenceManifestEntryRead[];
  coverage: CoverageMatrixRead;
  lifecycle_trail: LifecycleTrailEntryRead[];
  atos: DeploymentAuthorisationRead[];
}

export interface UseCaseExportRead extends UseCaseExportSectionsRead {
  audit_trail: AuditTrailEntryRead[];
  generated_at: string;
  content_hash: string;
}

// ---------------------------------------------------------------------------
// System export
// ---------------------------------------------------------------------------

export interface SystemExportRead {
  system_id: string;
  system: SystemDetail;
  use_cases: UseCaseExportSectionsRead[];
  system_coverage: CoverageMatrixRead;
  audit_trail: AuditTrailEntryRead[];
  generated_at: string;
  content_hash: string;
}

// ---------------------------------------------------------------------------
// Framework export
// ---------------------------------------------------------------------------

export interface FrameworkExportRead {
  framework: string;
  coverage: CoverageMatrixRead;
  substantiation_manifest: EvidenceManifestEntryRead[];
  generated_at: string;
  content_hash: string;
}

// ---------------------------------------------------------------------------
// ATO document
// ---------------------------------------------------------------------------

/** GET /v1/use-cases/{id}/authorisation/document — user-initiated only (INV-53).
 * basis_is_current_state_not_authorisation_snapshot is always true (D-34/INV-44);
 * the UI must always show the drift caveat — no conditional (DF6-5). */
export interface AtoDocumentRead {
  ato: DeploymentAuthorisationRead;
  current_assessment_summary: AssessmentRead;
  current_classification_summary: ClassificationHistoryEntryRead | null;
  basis_is_current_state_not_authorisation_snapshot: true;
}
