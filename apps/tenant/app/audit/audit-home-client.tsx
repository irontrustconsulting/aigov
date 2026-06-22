"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useMe } from "@/lib/intake";
import {
  useTenantCoverage,
  useFrameworkExport,
} from "@/lib/audit";
import { useEvidenceDetail } from "@/lib/evidence";
import {
  CoverageMatrix,
  AuditGradeDivider,
  AuditPackView,
} from "@irontrust/ui";

const FRAMEWORKS = ["ISO_42001", "EU_AI_ACT", "ISO_42005"] as const;
type Framework = (typeof FRAMEWORKS)[number];

/**
 * UI-F6-AUDITPACK: programme home.
 * Role branch via GET /v1/me (DF2-5):
 *   admin (zero gov roles) → empty-state, no coverage/export call
 *   any gov role → tenant coverage matrix + framework export + pack index
 */
export function AuditHomeClient() {
  const me = useMe();

  if (me.isLoading) return <p>Loading…</p>;
  if (me.isError || !me.data) return <p role="alert">Could not load your role.</p>;

  const roleKeys = me.data.governance_roles.map((r) => r.key);

  if (roleKeys.length === 0) {
    return (
      <main aria-label="audit-home">
        <h1>Audit programme</h1>
        <p>
          Your account doesn&apos;t hold a governance role. Control coverage and audit packs are not
          available. Contact a tenant admin to be assigned a governance role.
        </p>
      </main>
    );
  }

  return <AuditHome />;
}

function AuditHome() {
  const [includeUnapproved, setIncludeUnapproved] = useState(false);
  const [frameworkFilter, setFrameworkFilter] = useState<Framework | "">("");
  const [frameworkExportEnabled, setFrameworkExportEnabled] = useState(false);

  const coverageQuery = useTenantCoverage(frameworkFilter || undefined, includeUnapproved);
  const exportQuery = useFrameworkExport(frameworkFilter || "ISO_42001", frameworkExportEnabled);

  // Evidence download on-intent (DF5-3 / INV-22) — same pattern as evidence home.
  const [pendingDownloadId, setPendingDownloadId] = useState("");
  const detailQuery = useEvidenceDetail(pendingDownloadId, Boolean(pendingDownloadId));
  useEffect(() => {
    if (pendingDownloadId && detailQuery.data) {
      window.location.href = detailQuery.data.download_url;
      setPendingDownloadId("");
    }
  }, [pendingDownloadId, detailQuery.data]);

  return (
    <main aria-label="audit-home">
      <h1>Audit programme</h1>

      {/* ----------------------------------------------------------------- */}
      {/* Tenant coverage matrix                                              */}
      {/* ----------------------------------------------------------------- */}
      <section aria-label="tenant-coverage" className="mb-8">
        <h2 className="mb-2 text-lg font-semibold">Tenant coverage</h2>

        <label className="mb-3 flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={includeUnapproved}
            onChange={(e) => setIncludeUnapproved(e.target.checked)}
          />
          Include in-progress (not audit-grade)
        </label>

        {includeUnapproved && (
          <AuditGradeDivider label="Interactive posture — includes in-progress, not audit-grade" />
        )}

        {coverageQuery.isLoading && <p>Loading coverage…</p>}
        {coverageQuery.isError && (
          <p role="alert">Could not load coverage.</p>
        )}
        {coverageQuery.data && (
          <CoverageMatrix
            matrix={coverageQuery.data}
            label={includeUnapproved ? "Interactive posture (in-progress included)" : "Coverage"}
          />
        )}
      </section>

      {/* ----------------------------------------------------------------- */}
      {/* Framework export                                                    */}
      {/* ----------------------------------------------------------------- */}
      <section aria-label="framework-export" className="mb-8">
        <h2 className="mb-2 text-lg font-semibold">Framework audit pack</h2>

        <div className="mb-3 flex gap-3">
          <select
            aria-label="framework-select"
            value={frameworkFilter}
            onChange={(e) => {
              setFrameworkFilter(e.target.value as Framework | "");
              setFrameworkExportEnabled(false);
            }}
            className="border-border rounded border px-2 py-1 text-sm"
          >
            <option value="">— Select framework —</option>
            {FRAMEWORKS.map((f) => (
              <option key={f} value={f}>
                {f}
              </option>
            ))}
          </select>

          <button
            type="button"
            disabled={!frameworkFilter || exportQuery.isFetching}
            className="border-border rounded border px-3 py-1 text-sm disabled:opacity-50"
            onClick={() => setFrameworkExportEnabled(true)}
          >
            {exportQuery.isFetching ? "Generating…" : "Generate framework audit pack"}
          </button>
        </div>

        {exportQuery.isError && (
          <p role="alert">Could not generate the framework audit pack.</p>
        )}
        {exportQuery.data && (
          <AuditPackView
            pack={exportQuery.data}
            onDownloadEvidence={(id) => setPendingDownloadId(id)}
          />
        )}
      </section>

      {/* ----------------------------------------------------------------- */}
      {/* Pack index — navigation only, no coverage truth (DF6-9)            */}
      {/* ----------------------------------------------------------------- */}
      <section aria-label="pack-index" className="mb-8">
        <h2 className="mb-2 text-lg font-semibold">Pack index</h2>
        <ul className="space-y-1 text-sm">
          <li>
            <Link href="/systems" className="underline">
              System audit packs →
            </Link>
            <span className="text-text-muted ml-2">
              (navigate to a system to generate its pack)
            </span>
          </li>
          <li>
            <Link href="/use-cases" className="underline">
              Use-case audit packs →
            </Link>
            <span className="text-text-muted ml-2">
              (navigate to a use case to generate its pack)
            </span>
          </li>
        </ul>
      </section>
    </main>
  );
}
