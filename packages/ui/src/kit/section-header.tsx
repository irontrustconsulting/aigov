import { type ReactNode } from "react";

export interface SectionHeaderProps {
  title: string;
  /** Optional action (e.g. a link or button). */
  action?: ReactNode;
}

export function SectionHeader({ title, action }: SectionHeaderProps) {
  return (
    <div className="flex items-center justify-between gap-4">
      <h2 className="text-lg font-semibold text-ink">{title}</h2>
      {action && <div className="shrink-0">{action}</div>}
    </div>
  );
}
