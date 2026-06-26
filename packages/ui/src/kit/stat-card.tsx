import { type ReactNode } from "react";

export interface StatCardProps {
  label: string;
  value: string | number;
  /** Optional trend indicator (e.g. a VerdictChip or plain text). */
  trend?: ReactNode;
}

export function StatCard({ label, value, trend }: StatCardProps) {
  return (
    <div className="rounded-lg bg-paper px-4 py-4" style={{ boxShadow: "var(--elevation-raised)" }}>
      <p className="text-xs font-medium uppercase tracking-wide text-ink-muted">{label}</p>
      <div className="mt-1 flex items-end justify-between gap-2">
        <p className="text-2xl font-semibold text-ink">{value}</p>
        {trend && <div className="shrink-0 text-sm">{trend}</div>}
      </div>
    </div>
  );
}
