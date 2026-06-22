/**
 * String-literal mirrors of the backend's `str, enum.Enum` types
 * (app/models/base.py). Pydantic serialises these enums by VALUE, so these
 * are the lowercase wire values — distinct from the Postgres enum LABELS
 * (uppercase-by-name; see sprint §0.5's pg_enum footgun), which never reach
 * the client. The client renders what the API returns; it does not
 * reconstruct or guess casing.
 */

export type EUAIActTier =
  | "prohibited"
  | "high_risk"
  | "limited_risk"
  | "minimal_risk"
  | "unclassified"
  | "requires_context";

export type LifecycleState =
  | "requested"
  | "vendor_check"
  | "product_check"
  | "intake"
  | "halted_prohibited"
  | "under_assessment"
  | "treatment_pending"
  | "pending_authorisation"
  | "authorised"
  | "deployed";

export type ClassificationStatus =
  | "pending_review"
  | "approved"
  | "changes_requested"
  | "needs_refresh";

export type ProvenanceConfidence =
  | "ai_suggested"
  | "catalogue_curated"
  | "user_confirmed"
  | "user_amended"
  | "user_provided"; // section-answer / from-scratch item / snapshotted register fact

/** app/models/base.py SystemLifecycleStage — a fixed, small enum; option
 * list is enumerated client-side (no vocab table/route backs it, unlike the
 * six WI-0 vocab tables) per WI-5's plan. Confirm casing live against
 * pg_enum before relying on it (D-21 / the §0.5 footgun pattern). */
export type SystemLifecycleStage = "development" | "pilot" | "production" | "retired";

// ---------------------------------------------------------------------------
// Assessment enums (UI-F3-ASSESS) — wire values from app/models/base.py
// ---------------------------------------------------------------------------

export type AssessmentStatus = "draft" | "in_review" | "approved" | "needs_refresh";

export type AssessmentType = "aiia" | "fria" | "dpia" | "model_risk";

export type CoverageStatus = "open" | "partial" | "satisfied";

/** SectionApplicability wire value is "not_applicable" (NOT "n_a"). */
export type SectionApplicability = "required" | "recommended" | "not_applicable";

export type TreatmentDecision = "mitigate" | "accept" | "transfer" | "avoid";
