import { Button } from "../primitives/button";

export interface ResumePromptProps {
  /** The catalogue product name, or null for a custom / in-house system. */
  productName: string | null;
  /** The clamped step label to surface to the user (e.g. "intake"). */
  savedStep: string;
  /** ISO 8601 string from draft.updated_at. */
  lastEditedAt: string;
  onResume: () => void;
  onStartOver: () => void;
}

function formatDate(iso: string): string {
  try {
    return new Intl.DateTimeFormat(undefined, {
      dateStyle: "medium",
      timeStyle: "short",
    }).format(new Date(iso));
  } catch {
    return iso;
  }
}

export function ResumePrompt({
  productName,
  savedStep,
  lastEditedAt,
  onResume,
  onStartOver,
}: ResumePromptProps) {
  return (
    <div
      className="rounded-lg border border-hairline bg-paper p-6 space-y-4"
      style={{ boxShadow: "var(--elevation-raised)" }}
    >
      <div>
        <p className="text-lg font-semibold text-ink">
          Continue registering {productName ?? "your AI system"}
        </p>
        <p className="text-sm text-ink-muted mt-1">
          Last saved{" "}
          <time dateTime={lastEditedAt}>{formatDate(lastEditedAt)}</time>
          {" "}· Step: {savedStep}
        </p>
      </div>
      <div className="flex gap-3">
        <Button onClick={onResume}>Resume</Button>
        <Button variant="ghost" onClick={onStartOver}>
          Start over
        </Button>
      </div>
    </div>
  );
}
