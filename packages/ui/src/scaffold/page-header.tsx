import { type ReactNode } from "react";

export interface PageHeaderProps {
  title: string;
  subtitle?: string;
  /** Primary-action slot (e.g. a primary Button). */
  action?: ReactNode;
  /** Breadcrumb or step indicator slot. */
  breadcrumb?: ReactNode;
}

export function PageHeader({ title, subtitle, action, breadcrumb }: PageHeaderProps) {
  return (
    <div className="space-y-1">
      {breadcrumb && (
        <div className="text-sm text-ink-muted">{breadcrumb}</div>
      )}
      <div className="flex items-start justify-between gap-4">
        <div className="space-y-0.5">
          <h1 className="text-2xl font-semibold text-ink">{title}</h1>
          {subtitle && (
            <p className="text-sm text-ink-muted">{subtitle}</p>
          )}
        </div>
        {action && <div className="shrink-0">{action}</div>}
      </div>
    </div>
  );
}
