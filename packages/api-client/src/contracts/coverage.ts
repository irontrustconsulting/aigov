/** Coverage matrix — mirrors app/schemas/coverage.py (Sprint 7a). Response-only. */

export interface ContributingRefRead {
  item_id: string;
  assessment_id: string;
  governing_status: string;
}

export interface FrameworkMappingRead {
  framework: string;
  clause_ref: string;
}

export interface CoverageBreakdownRead {
  satisfied: number;
  partial: number;
  open: number;
  /** SATISFIED links downgraded to effective PARTIAL by require_evidence_for_satisfied
   * (internal to export; never a client param). Never folded into `partial`. */
  downgraded_unsubstantiated: number;
  contributing_refs: ContributingRefRead[];
}

export interface ControlCoverageRead {
  control_id: string;
  code: string;
  title: string;
  /** Plain string — UNADDRESSED has no DB enum label; never type-bind to CoverageStatus (DF6-3). */
  verdict: string;
  breakdown: CoverageBreakdownRead;
  framework_mappings: FrameworkMappingRead[];
}

export interface FrameworkClauseCoverageRead {
  framework: string;
  clause_ref: string;
  verdict: string;
  control_ids: string[];
}

export interface UnaddressedControlRead {
  control_id: string;
  code: string;
  title: string;
  framework_mappings: FrameworkMappingRead[];
}

export interface CoverageMatrixRead {
  scope: string;
  scope_id: string | null;
  framework_filter: string | null;
  include_unapproved: boolean;
  controls: ControlCoverageRead[];
  frameworks: FrameworkClauseCoverageRead[];
  unaddressed_controls: UnaddressedControlRead[];
  /** True until applicability layer (OPEN-3) lands. UI must show caveat + render as gaps,
   * never a fail denominator (INV-52, DF6-4). */
  not_an_obligation_set: boolean;
  generated_at: string;
}
