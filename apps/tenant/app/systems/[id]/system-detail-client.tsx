"use client";

import { useMe } from "@/lib/intake";
import { isYourCourt, resolveCourt, useSystemRollup } from "@/lib/portfolio";
import { WhoseCourtIndicator } from "@irontrust/ui";

/**
 * UI-F2-PORTFOLIO system drill-in: `GET /v1/systems/{id}/rollup` (live
 * state) — use cases, states, highest tier, per-use-case resolved court.
 *
 * No forward links into F1's wizard: `apps/tenant/app/systems/new`'s step
 * is plain in-memory `useReducer` state, never synced to the URL, so there
 * is no real per-use-case resumable destination to link to (confirmed at
 * this sprint's pre-flight). The blocking reason/court is rendered as
 * informational text only; resuming a specific use case is deferred
 * (STATE.md).
 */
export function SystemDetailClient({ systemId }: { systemId: string }) {
  const me = useMe();
  const rollup = useSystemRollup(systemId);

  if (me.isLoading || rollup.isLoading) return <p>Loading…</p>;
  if (me.isError || !me.data) return <p role="alert">Could not load your role.</p>;
  if (rollup.isError || !rollup.data) return <p role="alert">Could not load this system.</p>;

  const roleKeys = new Set(me.data.governance_roles.map((r) => r.key));

  return (
    <main>
      <h1>{rollup.data.system_name}</h1>
      <p>
        {rollup.data.use_case_count} use case{rollup.data.use_case_count === 1 ? "" : "s"}
        {rollup.data.highest_tier && <> · highest tier: {rollup.data.highest_tier}</>}
      </p>

      <ul aria-label="use-cases">
        {rollup.data.use_cases.map((useCase) => {
          const court = resolveCourt(useCase.blocking);
          return (
            <li key={useCase.use_case_id}>
              <h2>{useCase.title}</h2>
              <p>
                State: {useCase.state} · EU tier: {useCase.eu_tier}
              </p>
              {court ? (
                <p>
                  <WhoseCourtIndicator
                    partyLabel={court.partyLabel}
                    isYourCourt={isYourCourt(court, roleKeys)}
                  />{" "}
                  {court.reason}
                </p>
              ) : (
                <p>Nothing is blocking this use case right now.</p>
              )}
            </li>
          );
        })}
      </ul>
    </main>
  );
}
