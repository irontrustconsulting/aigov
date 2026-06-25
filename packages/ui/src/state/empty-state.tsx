import { type ReactNode } from "react";

export interface EmptyStateProps {
  icon?: ReactNode;
  message: string;
  action?: ReactNode;
}

export function EmptyState({ icon, message, action }: EmptyStateProps) {
  return (
    <div
      className="flex flex-col items-center gap-3 rounded-lg border border-hairline bg-surface-sunken px-6 py-10 text-center"
      role="status"
    >
      {icon && (
        <div className="text-ink-muted" aria-hidden="true">
          {icon}
        </div>
      )}
      <p className="text-sm text-ink-muted">{message}</p>
      {action && <div>{action}</div>}
    </div>
  );
}
