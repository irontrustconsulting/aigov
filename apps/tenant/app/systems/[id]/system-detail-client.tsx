"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useMe } from "@/lib/intake";
import { isYourCourt, resolveCourt, useSystemRollup } from "@/lib/portfolio";
import { useSystemCoverage, useSystemExport } from "@/lib/audit";
import { useEvidenceDetail } from "@/lib/evidence";
import { WhoseCourtIndicator, CoverageMatrix, AuditPackView } from "@irontrust/ui";

/**
 * UI-F2-PORTFOLIO system drill-in: `GET /v1/systems/{id}/rollup` (live
 * state) — use cases, states, highest tier, per-use-case resolved court.
 *
 * UI-F6-AUDITPACK (ALTER): coverage panel (eager, staleTime: 0) + system
 * export action (deliberate-only, INV-53). Admin → no coverage/export call.
 */
export function SystemDetailClient({ systemId }: { systemId: string }) {
  const me = useMe();
  const rollup = useSystemRollup(systemId);

  if (me.isLoading || rollup.isLoading) return <p>Loading…</p>;
  if (me.isError || !me.data) return <p role="alert">Could not load your role.</p>;
  if (rollup.isError || !rollup.data) return <p role="alert">Could not load this system.</p>;

  const roleKeys = new Set(me.data.governance_roles.map((r) => r.key));
  const hasGovRole = roleKeys.size > 0;

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
              <h2>
                <Link href={`/use-cases/${useCase.use_case_id}`}>{useCase.title}</Link>
              </h2>
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

      {/* Coverage + export — gov roles only (DF2-5 / V-2) */}
      {hasGovRole && <SystemAuditPanels systemId={systemId} />}
    </main>
  );
}

function SystemAuditPanels({ systemId }: { systemId: string }) {
  const coverageQuery = useSystemCoverage(systemId);
  const [exportEnabled, setExportEnabled] = useState(false);
  const exportQuery = useSystemExport(systemId, exportEnabled);

  // Evidence download on-intent (DF5-3 / INV-22).
  const [pendingDownloadId, setPendingDownloadId] = useState("");
  const detailQuery = useEvidenceDetail(pendingDownloadId, Boolean(pendingDownloadId));
  useEffect(() => {
    if (pendingDownloadId && detailQuery.data) {
      window.location.href = detailQuery.data.download_url;
      setPendingDownloadId("");
    }
  }, [pendingDownloadId, detailQuery.data]);

  return (
    <>
      <section aria-label="system-coverage" className="mt-6">
        <h2 className="mb-2 text-lg font-semibold">Control coverage</h2>
        {coverageQuery.isLoading && <p>Loading coverage…</p>}
        {coverageQuery.isError && <p role="alert">Could not load coverage.</p>}
        {coverageQuery.data && <CoverageMatrix matrix={coverageQuery.data} />}
      </section>

      <section aria-label="system-export" className="mt-6">
        <h2 className="mb-2 text-lg font-semibold">Audit pack</h2>
        <button
          type="button"
          disabled={exportQuery.isFetching}
          className="border-border rounded border px-3 py-1.5 text-sm disabled:opacity-50"
          onClick={() => setExportEnabled(true)}
        >
          {exportQuery.isFetching ? "Generating…" : "Generate system audit pack"}
        </button>
        {exportQuery.isError && <p role="alert">Could not generate the audit pack.</p>}
        {exportQuery.data && (
          <div className="mt-4">
            <AuditPackView
              pack={exportQuery.data}
              onDownloadEvidence={(id) => setPendingDownloadId(id)}
            />
          </div>
        )}
      </section>
    </>
  );
}
