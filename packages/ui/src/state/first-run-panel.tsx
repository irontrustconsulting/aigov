import { type ReactNode } from "react";

export interface FirstRunPanelProps {
  heading: string;
  body: string;
  action: ReactNode;
}

export function FirstRunPanel({ heading, body, action }: FirstRunPanelProps) {
  return (
    <div className="rounded-lg border border-hairline bg-surface px-6 py-8">
      <div className="space-y-4">
        <div className="space-y-1">
          <h2 className="text-lg font-semibold text-ink">{heading}</h2>
          <p className="text-sm text-ink-muted">{body}</p>
        </div>
        <div>{action}</div>
      </div>
    </div>
  );
}
