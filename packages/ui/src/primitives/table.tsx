import type { ReactNode } from "react";

export type TableDensity = "comfortable" | "compact";

export function Table({
  children,
  density = "comfortable",
}: {
  children: ReactNode;
  density?: TableDensity;
}) {
  return (
    <table
      className={[
        "w-full border-collapse",
        density === "comfortable" ? "text-sm" : "text-xs",
      ].join(" ")}
    >
      {children}
    </table>
  );
}

export function TableHeaderRow({
  children,
  density = "comfortable",
}: {
  children: ReactNode;
  density?: TableDensity;
}) {
  return (
    <thead className="bg-surface-sunken text-ink-muted">
      <tr>
        {children}
      </tr>
    </thead>
  );
}

export function TableRow({ children }: { children: ReactNode }) {
  return <tr className="border-b border-hairline">{children}</tr>;
}

export function TableCell({
  children,
  density = "comfortable",
}: {
  children: ReactNode;
  density?: TableDensity;
}) {
  return (
    <td className={density === "comfortable" ? "px-4 py-3" : "px-3 py-1.5"}>
      {children}
    </td>
  );
}

export function TableHeaderCell({
  children,
  density = "comfortable",
}: {
  children: ReactNode;
  density?: TableDensity;
}) {
  return (
    <th
      className={[
        "text-left font-medium",
        density === "comfortable" ? "px-4 py-3" : "px-3 py-1.5",
      ].join(" ")}
    >
      {children}
    </th>
  );
}
