import type { ReactNode } from "react";

export function Table({ children }: { children: ReactNode }) {
  return (
    <table className="border-border w-full border-collapse text-sm">{children}</table>
  );
}

export function TableHeaderRow({ children }: { children: ReactNode }) {
  return (
    <thead className="bg-surface text-text-muted">
      <tr>{children}</tr>
    </thead>
  );
}

export function TableRow({ children }: { children: ReactNode }) {
  return <tr className="border-border border-b">{children}</tr>;
}

export function TableCell({ children }: { children: ReactNode }) {
  return <td className="px-3 py-2">{children}</td>;
}
