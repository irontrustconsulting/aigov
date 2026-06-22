import type { CoverageMatrixRead } from "@irontrust/api-client";
import { NotAnObligationSetBanner } from "./not-an-obligation-set-banner";
import { Table, TableHeaderRow, TableRow, TableCell } from "../primitives/table";

interface Props {
  matrix: CoverageMatrixRead;
  /** Label shown above the table (e.g. "Interactive posture" vs "Audit-grade coverage"). */
  label?: string;
}

/** Verdict chip colours — UNADDRESSED is neutral; never merged with PARTIAL (INV-51, DF6-3). */
function VerdictChip({ verdict }: { verdict: string }) {
  const v = verdict.toUpperCase();
  const classMap: Record<string, string> = {
    SATISFIED: "bg-success-subtle text-success-fg border-success",
    PARTIAL: "bg-warning-subtle text-warning-fg border-warning",
    OPEN: "bg-error-subtle text-error-fg border-error",
    UNADDRESSED: "bg-surface-subtle text-text-muted border-border",
  };
  const cls = classMap[v] ?? classMap.UNADDRESSED;
  return (
    <span className={`rounded border px-2 py-0.5 text-xs font-medium ${cls}`}>
      {v}
    </span>
  );
}

function formatBytes(bytes: number | null): string {
  if (bytes === null) return "—";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/**
 * CoverageMatrix — renders a CoverageMatrixRead with:
 * - NotAnObligationSetBanner when not_an_obligation_set
 * - Per-control verdict chip + expandable breakdown disclosure
 * - downgraded_unsubstantiated rendered distinctly (INV-51)
 * - unaddressed_controls at bottom as gaps, not failures
 */
export function CoverageMatrix({ matrix, label }: Props) {
  return (
    <section aria-label={label ?? "coverage-matrix"}>
      {label && <h3 className="text-text mb-2 font-semibold">{label}</h3>}

      {matrix.not_an_obligation_set && (
        <div className="mb-3">
          <NotAnObligationSetBanner unaddressedControls={matrix.unaddressed_controls} />
        </div>
      )}

      {matrix.controls.length === 0 ? (
        <p className="text-text-muted text-sm">No controls in scope.</p>
      ) : (
        <Table>
          <TableHeaderRow>
            <th className="px-3 py-2 text-left font-medium">Code</th>
            <th className="px-3 py-2 text-left font-medium">Control</th>
            <th className="px-3 py-2 text-left font-medium">Verdict</th>
            <th className="px-3 py-2 text-left font-medium">Breakdown</th>
          </TableHeaderRow>
          {matrix.controls.map((ctrl) => (
            <TableRow key={ctrl.control_id}>
              <TableCell>
                <span className="font-mono text-xs">{ctrl.code}</span>
              </TableCell>
              <TableCell>{ctrl.title}</TableCell>
              <TableCell>
                <VerdictChip verdict={ctrl.verdict} />
              </TableCell>
              <TableCell>
                <details>
                  <summary className="cursor-pointer text-xs">
                    ✓{ctrl.breakdown.satisfied} ~{ctrl.breakdown.partial} ✗{ctrl.breakdown.open}
                    {ctrl.breakdown.downgraded_unsubstantiated > 0 && (
                      <span className="text-warning-fg ml-1">
                        ↓{ctrl.breakdown.downgraded_unsubstantiated} downgraded
                      </span>
                    )}
                  </summary>
                  <dl className="mt-1 text-xs">
                    <dt className="inline font-medium">Satisfied:</dt>{" "}
                    <dd className="inline">{ctrl.breakdown.satisfied}</dd>
                    <br />
                    <dt className="inline font-medium">Partial:</dt>{" "}
                    <dd className="inline">{ctrl.breakdown.partial}</dd>
                    <br />
                    <dt className="inline font-medium">Open:</dt>{" "}
                    <dd className="inline">{ctrl.breakdown.open}</dd>
                    {ctrl.breakdown.downgraded_unsubstantiated > 0 && (
                      <>
                        <br />
                        <dt className="text-warning-fg inline font-medium">
                          Downgraded (unsubstantiated):
                        </dt>{" "}
                        <dd className="text-warning-fg inline">
                          {ctrl.breakdown.downgraded_unsubstantiated}
                        </dd>
                      </>
                    )}
                  </dl>
                </details>
              </TableCell>
            </TableRow>
          ))}
        </Table>
      )}

      {!matrix.not_an_obligation_set && matrix.unaddressed_controls.length > 0 && (
        <div className="mt-3">
          <p className="text-text-muted text-sm font-medium">
            Controls not yet addressed ({matrix.unaddressed_controls.length}):
          </p>
          <ul className="text-text-muted mt-1 list-disc pl-5 text-xs">
            {matrix.unaddressed_controls.map((c) => (
              <li key={c.control_id}>
                <span className="font-mono">{c.code}</span> — {c.title}
              </li>
            ))}
          </ul>
        </div>
      )}

      <p className="text-text-muted mt-2 text-xs">
        Generated {new Date(matrix.generated_at).toLocaleString()}
        {matrix.framework_filter && ` · Framework: ${matrix.framework_filter}`}
        {matrix.include_unapproved && " · Includes in-progress (not audit-grade)"}
      </p>
    </section>
  );
}
