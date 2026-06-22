import type { GateResultRead } from "@irontrust/api-client";

/**
 * UI-F2-PORTFOLIO whose-court derivation (FE-11, D-38).
 *
 * Corrects the design doc's B1 hypothesis: live verification
 * (app/services/lifecycle_gates.py:158-166, classification_readiness) shows
 * the gate already disambiguates a REQUIRES_CONTEXT use case correctly —
 * "reviewer" while the classification snapshot is still PENDING_REVIEW,
 * "user" once it isn't. There is no `requires_context` field on the rollup
 * and no pre-branch is applied: court is read directly from
 * `blocking.responsible_party`, always.
 *
 * `responsible_party` (app/services/lifecycle_gates.py:44) is a distinct
 * vocabulary from governance roles (docs/DOMAIN.md §7) and must be mapped:
 * "user" is the use case owner/initiator, i.e. the `system_owner` role
 * (F1's whose-court-step.tsx already reads "user" as "With you"). "vendor"
 * and "system" are not governance roles and never match any caller — a use
 * case blocked on either is never "your court" for anyone.
 */
export type GovernanceRoleKey = "system_owner" | "contributor" | "reviewer" | "authoriser" | "auditor";

const PARTY_TO_ROLE: Record<string, GovernanceRoleKey | undefined> = {
  user: "system_owner",
  reviewer: "reviewer",
  authoriser: "authoriser",
};

const PARTY_LABEL: Record<string, string> = {
  user: "You (system owner)",
  reviewer: "Reviewer",
  authoriser: "Authoriser",
  vendor: "Vendor",
  system: "System",
};

export interface ResolvedCourt {
  party: string;
  partyLabel: string;
  roleKey: GovernanceRoleKey | null;
  reason: string;
}

/** `blocking` is the first non-"advance" gate result (or null if nothing is
 * blocking). Zero-use-case systems (A2) never have a `blocking` vector and
 * must not be passed here. */
export function resolveCourt(blocking: GateResultRead | null): ResolvedCourt | null {
  if (!blocking) return null;
  const party = blocking.responsible_party;
  return {
    party,
    partyLabel: PARTY_LABEL[party] ?? party,
    roleKey: PARTY_TO_ROLE[party] ?? null,
    reason: blocking.reason,
  };
}

/** Matches a resolved court against the caller's server-authoritative
 * governance role keys (GET /v1/me, D-24) — presentational only, the
 * backend remains the authz authority (FE-8). */
export function isYourCourt(court: ResolvedCourt | null, callerRoleKeys: ReadonlySet<string>): boolean {
  return court !== null && court.roleKey !== null && callerRoleKeys.has(court.roleKey);
}
