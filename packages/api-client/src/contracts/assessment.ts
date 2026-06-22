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
  SectionApplicability,
  TreatmentDecision,
} from "./enums";

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
