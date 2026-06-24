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
      {systemName && <p aria-label="system-name" className="text-ink-muted text-sm">{systemName}</p>}
      <h1 className="text-2xl font-semibold">{useCaseTitle}</h1>
      {euTier && (
        <p aria-label="eu-tier" className="flex flex-wrap items-center gap-2 text-sm mt-1">
          <TierBadge value={toTierMember(euTier)} variant="compact" />
        </p>
      )}

      {/* Auditor has no court row — they observe, not act (UI-F4-ASSURE WI-8) */}
      {branch !== "auditor" && (
        court ? (
          <p className="flex flex-wrap items-center gap-2 text-sm mt-1">
            <WhoseCourtIndicator
              partyLabel={court.partyLabel}
              isYourCourt={isYourCourt(court, roleKeys)}
            />{" "}
            {court.reason}
          </p>
        ) : (
          <p aria-label="court-status" className="text-ink-muted text-sm mt-1">No blocking gate at this time.</p>
        )
      )}

      {/* structural absence for non-system_owner (FE-8) */}
      <SodAction barred={!isSystemOwner}>
        <button
          onClick={() => reEvaluate.mutate()}
          disabled={reEvaluate.isPending}
          aria-busy={reEvaluate.isPending}
          className="border-hairline rounded border px-3 py-1.5 text-sm disabled:opacity-50 mt-2"
        >
          {reEvaluate.isPending ? "Re-evaluating…" : "Re-evaluate"}
        </button>
      </SodAction>
    </header>
  );
}
