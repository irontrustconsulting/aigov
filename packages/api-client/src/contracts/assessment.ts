/**
 * UI-F3-ASSESS contract types — mirrors app/schemas/assessment.py.
 * Pydantic serialises enums by VALUE (lowercase wire values).
 * Provenance is never accepted as request input (INV-13); it is omitted from
 * all mutation body types. lock_version is in the response body, not ETag-only.
 */

import type {
  AssessmentStatus,
  AssessmentType,
  CoverageStatus,
  EUAIActTier,
  ProvenanceConfidence,
  ReviewDecision,
  SectionApplicability,
  TreatmentDecision,
} from "./enums";
import type { ItemEvidenceRead } from "./evidence";

// ---------------------------------------------------------------------------
// Control links
// ---------------------------------------------------------------------------

export interface ControlLinkRead {
  id: string;
  item_id: string;
  control_id: string;
  coverage: CoverageStatus;
}

export interface ControlLinkCreate {
  control_id: string;
  coverage?: CoverageStatus;
}

// ---------------------------------------------------------------------------
// Assessment items
// ---------------------------------------------------------------------------

export interface AssessmentItemRead {
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
  treatment_decision: TreatmentDecision | null;
  treatment_rationale: string | null;
  provenance: ProvenanceConfidence;
  selection_basis: string | null;
  source_ref: string | null;
  lock_version: number;
  created_at: string;
  updated_at: string;
  source_assessment_id: string | null;
  source_type: AssessmentType | null;
  control_links: ControlLinkRead[];
  /** Batch-loaded manifest (WI-F / DF5-8). No download_url — no evidence.access triggered. */
  evidence_links: ItemEvidenceRead[];
}

/** PATCH body — authoring fields only. Never include provenance (INV-13). */
export interface AssessmentItemAmend {
  response?: string | null;
  likelihood?: number | null;
  severity?: number | null;
  residual_likelihood?: number | null;
  residual_severity?: number | null;
  mitigation_plan?: string | null;
  treatment_decision?: TreatmentDecision | null;
  treatment_rationale?: string | null;
}

export interface AssessmentItemCreate {
  section_key: string;
  response?: string | null;
}

// ---------------------------------------------------------------------------
// Assessment (AIIA / feeder)
// ---------------------------------------------------------------------------

export interface AssessmentRead {
  id: string;
  use_case_id: string;
  type: AssessmentType;
  parent_aiia_id: string | null;
  status: AssessmentStatus;
  version: number;
  tier_snapshot: EUAIActTier;
  classification_version: number;
  is_current: boolean;
  lock_version: number;
  submission_round: number;
  submitted_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface AssessmentDetail extends AssessmentRead {
  items: AssessmentItemRead[];
  /** WI-9b: review history rows (reviewer_display_name from INV-34 join, D-25). */
  reviews: AssessmentReviewRead[];
}

// ---------------------------------------------------------------------------
// Review (UI-F4-ASSURE)
// ---------------------------------------------------------------------------

/** One review decision row for the attributed review-history display. */
export interface AssessmentReviewRead {
  id: string;
  assessment_id: string;
  reviewer_display_name: string | null;
  decision: ReviewDecision;
  note: string | null;
  submission_round: number;
  created_at: string;
}

/** POST /assessments/{id}/review body. note required when decision = "changes_requested". */
export interface AssessmentReviewCreate {
  decision: ReviewDecision;
  note?: string | null;
}

// ---------------------------------------------------------------------------
// Review queue (UI-F4-ASSURE)
// ---------------------------------------------------------------------------

export interface ReviewQueueEntryRead {
  assessment_id: string;
  use_case_id: string;
  tier_snapshot: EUAIActTier;
  submitted_by_name: string | null;
  submitted_by_email: string | null;
  submitted_at: string | null;
}

// ---------------------------------------------------------------------------
// Authorisation / ATO (UI-F4-ASSURE)
// ---------------------------------------------------------------------------

/** POST /use-cases/{id}/authorise body. */
export interface AuthoriseRequest {
  residual_risk_statement: string;
}

/** GET /use-cases/{id}/authorisation response.
 * live_state reflects the current vector — never read "authorised" from row
 * existence alone (INV-32). authorised_by_name from INV-34 join. */
export interface DeploymentAuthorisationRead {
  id: string;
  use_case_id: string;
  assessment_id: string;
  submission_round: number;
  tier: string;
  assessment_version: number;
  authorised_by_name: string | null;
  authorised_by_email: string | null;
  authorised_at: string;
  residual_risk_statement: string;
  live_state: string;
}

// ---------------------------------------------------------------------------
// Classification sign-off (UI-F4-ASSURE)
// ---------------------------------------------------------------------------

/** POST /use-cases/{id}/classification/sign-off response. */
export interface SignOffRead {
  id: string;
  use_case_id: string;
  tier: string;
  status: string;
  version: number;
  updated_at: string;
}

// ---------------------------------------------------------------------------
// Sections
// ---------------------------------------------------------------------------

export interface SectionRead {
  section_key: string;
  title: string;
  applicability: SectionApplicability;
  prompt: string | null;
  iso_42005_clause: string | null;
  instantiated: boolean;
  item_id: string | null;
}

// ---------------------------------------------------------------------------
// Feeder recommendations
// ---------------------------------------------------------------------------

export interface FeederRecommendationRead {
  type: AssessmentType;
  applicability: SectionApplicability;
  basis: string;
  exists: boolean;
}

// ---------------------------------------------------------------------------
// Reference: risks and controls (GET /reference/risks|controls)
// ---------------------------------------------------------------------------

export interface RiskRead {
  id: string;
  code: string;
  title: string;
  description: string | null;
  layer: string;
  source: string;
  source_ref: string | null;
  reference_url: string | null;
}

export interface ControlFrameworkMapRead {
  framework: string;
  clause_ref: string;
}

export interface ControlRead {
  id: string;
  code: string;
  title: string;
  description: string | null;
  version: number;
  frameworks: ControlFrameworkMapRead[];
}
