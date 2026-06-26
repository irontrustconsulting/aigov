/**
 * FE-16 ALTER / D-60: Authored humanized labels for the five verdict-family enums.
 * Keys are the wire .value exactly as the server emits them (lowercase snake_case).
 * Never .toUpperCase() the key — DF-V2-4, D-48.
 *
 * 25 unique keys; shared values (approved, needs_refresh) resolve to one label each.
 * British spelling, domain phrasing, acronyms preserved (Appendix D).
 */
export const LABEL_MAP: Record<string, string> = {
  /* approval_status */
  not_started: "Not started",
  under_review: "Under review",
  approved: "Approved",
  rejected: "Rejected",
  expired: "Expired",

  /* assessment_status */
  draft: "Draft",
  in_review: "In review",
  needs_refresh: "Needs refresh",

  /* classification_status */
  pending_review: "Pending review",
  changes_requested: "Changes requested",

  /* coverage_status */
  open: "Open",
  partial: "Partial",
  satisfied: "Satisfied",

  /* lifecycle_state */
  requested: "Requested",
  vendor_check: "Vendor check",
  product_check: "Product check",
  intake: "Intake",
  halted_prohibited: "Halted (prohibited)",
  under_assessment: "Under assessment",
  treatment_pending: "Treatment pending",
  pending_authorisation: "Pending authorisation",
  authorised: "Authorised",
  deployed: "Deployed",
  held: "Held",
  retired: "Retired",
};
