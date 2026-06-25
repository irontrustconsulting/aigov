import { type ReactNode } from "react";
import { Table, TableBody, TableHeaderRow, type TableDensity } from "../primitives/table";
import { EmptyState } from "../state/empty-state";

export interface DataTableProps {
  children: ReactNode;
  density?: TableDensity;
}

export interface DataTableHeaderProps {
  children: ReactNode;
  density?: TableDensity;
}

export interface DataTableBodyProps {
  children: ReactNode;
  /** When no rows are provided, renders this EmptyState message instead of an empty tbody. */
  emptyMessage?: string;
}

/** DataTable — scaffold wrapper over Table/TableBody (INV-66). Adds border,
 *  density control at the wrapper level, and an empty-body EmptyState. */
export function DataTable({ children, density }: DataTableProps) {
  return (
    <div className="overflow-hidden rounded-lg border border-hairline">
      <Table density={density}>{children}</Table>
    </div>
  );
}

export function DataTableHeader({ children, density }: DataTableHeaderProps) {
  return <TableHeaderRow density={density}>{children}</TableHeaderRow>;
}

export function DataTableBody({ children, emptyMessage }: DataTableBodyProps) {
  const hasRows =
    Array.isArray(children)
      ? children.some(Boolean)
      : Boolean(children);

  if (!hasRows && emptyMessage) {
    return (
      <TableBody>
        <tr>
          <td colSpan={99}>
            <EmptyState message={emptyMessage} />
          </td>
        </tr>
      </TableBody>
    );
  }

  return <TableBody>{children}</TableBody>;
}
