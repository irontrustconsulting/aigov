import type { CoverageMatrixRead } from "@irontrust/api-client";
import { NotAnObligationSetBanner } from "./not-an-obligation-set-banner";
import { Table, TableBody, TableHeaderRow, TableRow, TableCell, TableHeaderCell } from "../primitives/table";
import { VerdictChip } from "../status/verdict-chip";

function formatBytes(bytes: number | null): string {
  if (bytes === null) return "—";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

interface Props {
  matrix: CoverageMatrixRead;
  label?: string;
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
      {label && <h3 className="text-ink mb-2 font-semibold">{label}</h3>}

      {matrix.not_an_obligation_set && (
        <div className="mb-3">
          <NotAnObligationSetBanner unaddressedControls={matrix.unaddressed_controls} />
        </div>
      )}

      {matrix.controls.length === 0 ? (
        <p className="text-ink-muted text-sm">No controls in scope.</p>
      ) : (
        <Table>
          <TableHeaderRow>
            <TableHeaderCell>Code</TableHeaderCell>
            <TableHeaderCell>Control</TableHeaderCell>
            <TableHeaderCell>Verdict</TableHeaderCell>
            <TableHeaderCell>Breakdown</TableHeaderCell>
          </TableHeaderRow>
          <TableBody>
          {matrix.controls.map((ctrl) => (
            <TableRow key={ctrl.control_id}>
              <TableCell>
                <span className="font-mono text-xs">{ctrl.code}</span>
              </TableCell>
              <TableCell>{ctrl.title}</TableCell>
              <TableCell>
                {ctrl.verdict === "downgraded_unsubstantiated" ? (
                  <>
                    <VerdictChip value="PARTIAL" />
                    <span
                      data-verdict="downgraded"
                      className="ml-1 text-xs text-ink-muted"
                    >
                      downgraded
                    </span>
                  </>
                ) : (
                  <VerdictChip value={ctrl.verdict} />
                )}
              </TableCell>
              <TableCell>
                <details>
                  <summary className="cursor-pointer text-xs text-ink-muted">
                    ✓{ctrl.breakdown.satisfied} ~{ctrl.breakdown.partial} ✗{ctrl.breakdown.open}
                    {ctrl.breakdown.downgraded_unsubstantiated > 0 && (
                      <span className="ml-1" style={{ color: "var(--verdict-attention)" }}>
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
                        <dt
                          className="inline font-medium"
                          style={{ color: "var(--verdict-attention)" }}
                        >
                          Downgraded (unsubstantiated):
                        </dt>{" "}
                        <dd className="inline" style={{ color: "var(--verdict-attention)" }}>
                          {ctrl.breakdown.downgraded_unsubstantiated}
                        </dd>
                      </>
                    )}
                  </dl>
                </details>
              </TableCell>
            </TableRow>
          ))}
          </TableBody>
        </Table>
      )}

      {!matrix.not_an_obligation_set && matrix.unaddressed_controls.length > 0 && (
        <div className="mt-3">
          <p className="text-ink-muted text-sm font-medium">
            Controls not yet addressed ({matrix.unaddressed_controls.length}):
          </p>
          <ul className="text-ink-muted mt-1 list-disc pl-5 text-xs">
            {matrix.unaddressed_controls.map((c) => (
              <li key={c.control_id}>
                <span className="font-mono">{c.code}</span> — {c.title}
              </li>
            ))}
          </ul>
        </div>
      )}

      <p className="text-ink-muted mt-2 text-xs">
        Generated {new Date(matrix.generated_at).toLocaleString()}
        {matrix.framework_filter && ` · Framework: ${matrix.framework_filter}`}
        {matrix.include_unapproved && " · Includes in-progress (not audit-grade)"}
      </p>
    </section>
  );
}
