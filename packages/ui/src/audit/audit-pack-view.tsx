import type {
  UseCaseExportRead,
  SystemExportRead,
  FrameworkExportRead,
  UseCaseExportSectionsRead,
  ActorRef,
  AuditTrailEntryRead,
  LifecycleTrailEntryRead,
  ClassificationHistoryEntryRead,
} from "@irontrust/api-client";
import { CoverageMatrix } from "./coverage-matrix";
import { AuditGradeDivider } from "./audit-grade-divider";
import { EvidenceManifestTable } from "./evidence-manifest-table";
import { Table, TableBody, TableHeaderRow, TableRow, TableCell } from "../primitives/table";

interface Props {
  pack: UseCaseExportRead | SystemExportRead | FrameworkExportRead;
  /** Caller constructs GET /v1/evidence/{id} on-intent (INV-40, DF5-3). */
  onDownloadEvidence: (id: string) => void;
}

/** §4.5 actor attribution rule: name/email when present; bare user_id when null;
 * never fabricate a name (D-25). */
function renderActor(actor: ActorRef | null | undefined): string {
  if (!actor) return "(system)";
  return actor.name ?? actor.email ?? actor.user_id ?? "(system)";
}

function LifecycleTrailSection({ entries }: { entries: LifecycleTrailEntryRead[] }) {
  if (entries.length === 0) return <p className="text-ink-muted text-sm">No lifecycle trail.</p>;
  return (
    <Table>
      <TableHeaderRow>
        <th className="px-3 py-2 text-left font-medium">From</th>
        <th className="px-3 py-2 text-left font-medium">To</th>
        <th className="px-3 py-2 text-left font-medium">When</th>
        <th className="px-3 py-2 text-left font-medium">Actor</th>
        <th className="px-3 py-2 text-left font-medium">Reason</th>
      </TableHeaderRow>
      <TableBody>
        {entries.map((e, i) => (
          <TableRow key={i}>
            <TableCell>{e.from_state ?? "—"}</TableCell>
            <TableCell>{e.to_state}</TableCell>
            <TableCell>{new Date(e.occurred_at).toLocaleString()}</TableCell>
            <TableCell>{renderActor(e.actor)}</TableCell>
            <TableCell>{e.reason ?? "—"}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

function AuditTrailSection({ entries }: { entries: AuditTrailEntryRead[] }) {
  if (entries.length === 0) return <p className="text-ink-muted text-sm">No audit trail.</p>;
  return (
    <Table>
      <TableHeaderRow>
        <th className="px-3 py-2 text-left font-medium">Action</th>
        <th className="px-3 py-2 text-left font-medium">When</th>
        <th className="px-3 py-2 text-left font-medium">Actor</th>
        <th className="px-3 py-2 text-left font-medium">Entity type</th>
      </TableHeaderRow>
      <TableBody>
        {entries.map((e, i) => (
          <TableRow key={i}>
            <TableCell><span className="font-mono text-xs">{e.action}</span></TableCell>
            <TableCell>{new Date(e.occurred_at).toLocaleString()}</TableCell>
            <TableCell>{renderActor(e.actor)}</TableCell>
            <TableCell>{e.entity_type}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

function ClassificationHistorySection({ entries }: { entries: ClassificationHistoryEntryRead[] }) {
  if (entries.length === 0) return <p className="text-ink-muted text-sm">No classification history.</p>;
  return (
    <Table>
      <TableHeaderRow>
        <th className="px-3 py-2 text-left font-medium">Version</th>
        <th className="px-3 py-2 text-left font-medium">Tier</th>
        <th className="px-3 py-2 text-left font-medium">Status</th>
        <th className="px-3 py-2 text-left font-medium">Overridden</th>
        <th className="px-3 py-2 text-left font-medium">Signed off by</th>
      </TableHeaderRow>
      <TableBody>
        {entries.map((e, i) => (
          <TableRow key={i}>
            <TableCell>{e.version}</TableCell>
            <TableCell>{e.tier}</TableCell>
            <TableCell>{e.status}</TableCell>
            <TableCell>{e.overridden ? "Yes" : "No"}</TableCell>
            <TableCell>{e.signed_off_by ? renderActor(e.signed_off_by) : "—"}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

function UseCaseSections({
  sections,
  onDownloadEvidence,
}: {
  sections: UseCaseExportSectionsRead;
  onDownloadEvidence: (id: string) => void;
}) {
  return (
    <div className="space-y-6">
      <section aria-label="classification-history">
        <h4 className="mb-2 font-semibold">Classification History</h4>
        <ClassificationHistorySection entries={sections.classification_history} />
      </section>

      <section aria-label="assessment-section">
        <h4 className="mb-2 font-semibold">Assessment</h4>
        {sections.assessment.aiia_id ? (
          <>
            <p className="text-ink-muted mb-2 text-sm">
              AIIA status: {sections.assessment.status ?? "—"} · Items:{" "}
              {sections.assessment.native_items.length} native
              {sections.assessment.feeders.length > 0
                ? ` + ${sections.assessment.feeders.length} feeder(s)`
                : ""}
            </p>
            {sections.assessment.feeders.map((f) => (
              <details key={f.assessment_id} className="mt-2">
                <summary className="cursor-pointer text-sm">
                  Feeder: {f.type} ({f.status})
                </summary>
                <p className="text-ink-muted mt-1 pl-4 text-xs">
                  {f.items.length} items
                  {f.items.some((i) => i.surfaces_into) &&
                    ` (some surface into AIIA)`}
                </p>
              </details>
            ))}
          </>
        ) : (
          <p className="text-ink-muted text-sm">No AIIA on record.</p>
        )}
      </section>

      <section aria-label="evidence-manifest">
        <h4 className="mb-2 font-semibold">Evidence Manifest</h4>
        <EvidenceManifestTable
          entries={sections.evidence_manifest}
          onDownload={onDownloadEvidence}
        />
      </section>

      <section aria-label="audit-grade-coverage">
        <AuditGradeDivider />
        <CoverageMatrix matrix={sections.coverage} label="Audit-grade coverage" />
      </section>

      <section aria-label="lifecycle-trail">
        <h4 className="mb-2 font-semibold">Lifecycle Trail</h4>
        <LifecycleTrailSection entries={sections.lifecycle_trail} />
      </section>

      <section aria-label="atos">
        <h4 className="mb-2 font-semibold">
          ATOs ({sections.atos.length})
        </h4>
        {sections.atos.length === 0 ? (
          <p className="text-ink-muted text-sm">No ATOs on record.</p>
        ) : (
          <ul className="space-y-2 text-sm">
            {sections.atos.map((ato) => (
              <li key={ato.id} className="border-hairline rounded border px-3 py-2">
                Round {ato.submission_round} · {ato.tier} · authorised by{" "}
                {ato.authorised_by_name ?? "—"} on{" "}
                {new Date(ato.authorised_at).toLocaleDateString()}
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

/**
 * AuditPackView — sectioned renderer for audit pack exports (DF6-6).
 * Print-friendly layout; content_hash + generated_at in footer (INV-43/D-30).
 * Discriminates pack type via duck-typing.
 */
export function AuditPackView({ pack, onDownloadEvidence }: Props) {
  const isFramework = "substantiation_manifest" in pack;
  const isSystem = !isFramework && "system_id" in pack && "use_cases" in pack;
  const isUseCase = !isFramework && !isSystem && "use_case_id" in pack;

  return (
    <article aria-label="audit-pack-view" className="font-serif space-y-6">
      {/* Print trigger (DF6-6) */}
      <div className="flex justify-end print:hidden">
        <button
          type="button"
          className="border-hairline rounded border px-3 py-1.5 text-sm"
          onClick={() => window.print()}
        >
          Print / Save as PDF
        </button>
      </div>

      {isFramework && (
        <>
          <section aria-label="framework-coverage">
            <h3 className="mb-2 font-semibold">
              Framework: {(pack as FrameworkExportRead).framework}
            </h3>
            <AuditGradeDivider />
            <CoverageMatrix
              matrix={(pack as FrameworkExportRead).coverage}
              label="Audit-grade coverage"
            />
          </section>
          <section aria-label="substantiation-manifest">
            <h3 className="mb-2 font-semibold">Substantiation Manifest</h3>
            <EvidenceManifestTable
              entries={(pack as FrameworkExportRead).substantiation_manifest}
              onDownload={onDownloadEvidence}
            />
          </section>
        </>
      )}

      {isSystem && (() => {
        const s = pack as SystemExportRead;
        return (
          <>
            <section aria-label="system-context">
              <h3 className="mb-1 font-semibold">{s.system.name}</h3>
              <p className="text-ink-muted text-sm">
                {s.system.use_case_count} use case
                {s.system.use_case_count === 1 ? "" : "s"}
              </p>
            </section>
            <section aria-label="system-coverage">
              <h3 className="mb-2 font-semibold">System-level coverage</h3>
              <AuditGradeDivider />
              <CoverageMatrix matrix={s.system_coverage} label="Audit-grade coverage" />
            </section>
            {s.use_cases.map((uc) => (
              <section key={uc.use_case_id} aria-label={`use-case-${uc.use_case_id}`} className="border-hairline rounded border p-4">
                <h3 className="mb-4 font-semibold">Use case: {uc.use_case_id}</h3>
                <UseCaseSections sections={uc} onDownloadEvidence={onDownloadEvidence} />
              </section>
            ))}
            <section aria-label="audit-trail">
              <h3 className="mb-2 font-semibold">Audit Trail</h3>
              <AuditTrailSection entries={s.audit_trail} />
            </section>
          </>
        );
      })()}

      {isUseCase && (() => {
        const u = pack as UseCaseExportRead;
        return (
          <>
            <section aria-label="system-context">
              <h3 className="mb-1 font-semibold">{u.system.name}</h3>
            </section>
            <UseCaseSections sections={u} onDownloadEvidence={onDownloadEvidence} />
            <section aria-label="audit-trail">
              <h3 className="mb-2 font-semibold">Audit Trail</h3>
              <AuditTrailSection entries={u.audit_trail} />
            </section>
          </>
        );
      })()}

      {/* Footer — content_hash + generated_at (INV-43/D-30) */}
      {"content_hash" in pack && (
        <footer
          aria-label="pack-footer"
          className="border-hairline text-ink-muted border-t pt-4 text-xs"
        >
          <p>
            Generated: {new Date((pack as { generated_at: string }).generated_at).toLocaleString()}
          </p>
          <p className="font-mono">
            SHA-256: {(pack as { content_hash: string }).content_hash}
          </p>
        </footer>
      )}
    </article>
  );
}
