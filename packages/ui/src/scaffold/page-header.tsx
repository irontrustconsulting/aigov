import { ChevronLeft } from "lucide-react";
import { type ReactNode } from "react";

export interface PageHeaderProps {
  title: string;
  subtitle?: string;
  /** Primary-action slot (e.g. a primary Button). */
  action?: ReactNode;
  /** Breadcrumb or step indicator slot. */
  breadcrumb?: ReactNode;
  /** Back/up affordance (FE-21 ALTER). When provided, renders a chevron-left button before the title. */
  onBack?: () => void;
}

export function PageHeader({ title, subtitle, action, breadcrumb, onBack }: PageHeaderProps) {
  return (
    <div className="space-y-1">
      {breadcrumb && (
        <div className="text-sm text-ink-muted">{breadcrumb}</div>
      )}
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-start gap-2">
          {onBack && (
            <button
              type="button"
              onClick={onBack}
              aria-label="Go back"
              className="mt-1 rounded p-0.5 text-ink-muted transition-colors hover:bg-surface-sunken hover:text-ink"
            >
              <ChevronLeft className="h-5 w-5" aria-hidden="true" />
            </button>
          )}
          <div className="space-y-0.5">
            <h1 className="text-2xl font-semibold text-ink">{title}</h1>
            {subtitle && (
              <p className="text-sm text-ink-muted">{subtitle}</p>
            )}
          </div>
        </div>
        {action && <div className="shrink-0">{action}</div>}
      </div>
    </div>
  );
}
