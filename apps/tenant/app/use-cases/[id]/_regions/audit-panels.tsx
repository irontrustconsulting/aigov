"use client";

import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useUseCaseCoverage, useUseCaseExport, useAtoDocument } from "@/lib/audit";
import { useEvidenceDetail } from "@/lib/evidence";
import { CoverageMatrix, AuditPackView, AtoDocumentView } from "@irontrust/ui";

interface Props {
  useCaseId: string;
  /** Assessment ID of the governing AIIA, or null if none exists. */
  assessmentId: string | null;
  /** Status of the governing AIIA — coverage gated to APPROVED (INV-38/DF3-2). */
  assessmentStatus: string | null;
  /** False for admin callers (zero gov roles) — renders nothing. */
  canView: boolean;
}

/**
 * UI-F6-AUDITPACK: per-use-case audit panels region.
 * - Coverage: only when governing AIIA is APPROVED; else empty-state.
 * - Use-case export: deliberate-only (INV-53).
 * - ATO document: deliberate-only; ?round=N deep-link honoured (DF6-10).
 *   404 → "never authorised" empty-state. No round enumeration call.
 */
export function AuditPanels({ useCaseId, assessmentId, assessmentStatus, canView }: Props) {
  if (!canView) return null;

  return <AuditPanelsInner
    useCaseId={useCaseId}
    assessmentId={assessmentId}
    assessmentStatus={assessmentStatus}
  />;
}

function AuditPanelsInner({
  useCaseId,
  assessmentId,
  assessmentStatus,
}: {
  useCaseId: string;
  assessmentId: string | null;
  assessmentStatus: string | null;
}) {
  const searchParams = useSearchParams();
  const roundParam = searchParams.get("round");
  const round = roundParam !== null ? parseInt(roundParam, 10) : undefined;

  const isApproved = assessmentStatus === "approved";

  // Coverage — only when APPROVED (INV-38/DF3-2). Never fetches when not approved.
  const coverageQuery = useUseCaseCoverage(
    isApproved && assessmentId ? assessmentId : "",
    undefined,
    false
  );

  // Use-case export — deliberate only (INV-53).
  const [exportEnabled, setExportEnabled] = useState(false);
  const exportQuery = useUseCaseExport(useCaseId, exportEnabled);

  // ATO document — deliberate only; ?round=N deep-link (DF6-10).
  const [atoEnabled, setAtoEnabled] = useState(false);
  const atoQuery = useAtoDocument(useCaseId, atoEnabled, round);

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
    <div className="mt-6 space-y-6">
      {/* ----------------------------------------------------------------- */}
      {/* Coverage panel — APPROVED AIIA only                                */}
      {/* ----------------------------------------------------------------- */}
      <section aria-label="use-case-coverage">
        <h2 className="mb-2 font-semibold">Control coverage</h2>
        {!isApproved || !assessmentId ? (
          <p className="text-text-muted text-sm">
            Coverage available after AIIA approval.
          </p>
        ) : (
          <>
            {coverageQuery.isLoading && <p>Loading coverage…</p>}
            {coverageQuery.isError && <p role="alert">Could not load coverage.</p>}
            {coverageQuery.data && <CoverageMatrix matrix={coverageQuery.data} />}
          </>
        )}
      </section>

      {/* ----------------------------------------------------------------- */}
      {/* Use-case export                                                     */}
      {/* ----------------------------------------------------------------- */}
      <section aria-label="use-case-export">
        <h2 className="mb-2 font-semibold">Use-case audit pack</h2>
        <button
          type="button"
          disabled={exportQuery.isFetching}
          className="border-border rounded border px-3 py-1.5 text-sm disabled:opacity-50"
          onClick={() => setExportEnabled(true)}
        >
          {exportQuery.isFetching ? "Generating…" : "Generate use-case audit pack"}
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

      {/* ----------------------------------------------------------------- */}
      {/* ATO document                                                        */}
      {/* ----------------------------------------------------------------- */}
      <section aria-label="ato-document-section">
        <h2 className="mb-2 font-semibold">
          ATO document{round !== undefined ? ` (round ${round})` : " (latest)"}
        </h2>
        {!atoEnabled ? (
          <button
            type="button"
            className="border-border rounded border px-3 py-1.5 text-sm"
            onClick={() => setAtoEnabled(true)}
          >
            View ATO document
          </button>
        ) : (
          <>
            {atoQuery.isLoading && <p>Loading ATO document…</p>}
            {atoQuery.isError &&
              ((atoQuery.error as { status?: number })?.status === 404 ? (
                <p className="text-text-muted text-sm">
                  This use case has never been authorised.
                </p>
              ) : (
                <p role="alert">Could not load the ATO document.</p>
              ))}
            {atoQuery.data && <AtoDocumentView doc={atoQuery.data} />}
          </>
        )}
      </section>
    </div>
  );
}
