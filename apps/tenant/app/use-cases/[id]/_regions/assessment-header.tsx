"use client";

import { SodAction, WhoseCourtIndicator, TierBadge, toTierMember } from "@irontrust/ui";
import { useReEvaluate } from "@/lib/assess";
import { isYourCourt, type ResolvedCourt } from "@/lib/portfolio";
import type { EUAIActTier } from "@irontrust/api-client";
import type { RoleBranch } from "../assessment-page-client";

interface Props {
  useCaseId: string;
  useCaseTitle: string;
  euTier: EUAIActTier | null;
  systemName: string | null;
  court: ResolvedCourt | null;
  roleKeys: Set<string>;
  branch: RoleBranch;
}

/**
 * Use-case header: identity + whose-court + re-evaluate lever.
 * Court sourced only from lifecycle (FE-11): never inferred client-side.
 * re-evaluate is system_owner-only (FE-8 structural: absent for all other branches).
 * Auditor: no court row (they don't act; court is irrelevant to their view).
 */
export function AssessmentHeader({
  useCaseId,
  useCaseTitle,
  euTier,
  systemName,
  court,
  roleKeys,
  branch,
}: Props) {
  const reEvaluate = useReEvaluate(useCaseId);
  const isSystemOwner = branch === "system_owner";

  return (
    <header>
      {systemName && <p aria-label="system-name">{systemName}</p>}
      <h1>{useCaseTitle}</h1>
      {euTier && (
        <p aria-label="eu-tier">
          <TierBadge value={toTierMember(euTier)} variant="compact" />
        </p>
      )}

      {/* Auditor has no court row — they observe, not act (UI-F4-ASSURE WI-8) */}
      {branch !== "auditor" && (
        court ? (
          <p>
            <WhoseCourtIndicator
              partyLabel={court.partyLabel}
              isYourCourt={isYourCourt(court, roleKeys)}
            />{" "}
            {court.reason}
          </p>
        ) : (
          <p aria-label="court-status">No blocking gate at this time.</p>
        )
      )}

      {/* structural absence for non-system_owner (FE-8) */}
      <SodAction barred={!isSystemOwner}>
        <button
          onClick={() => reEvaluate.mutate()}
          disabled={reEvaluate.isPending}
          aria-busy={reEvaluate.isPending}
        >
          {reEvaluate.isPending ? "Re-evaluating…" : "Re-evaluate"}
        </button>
      </SodAction>
    </header>
  );
}
