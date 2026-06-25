import { AlertCircle } from "lucide-react";

export interface ErrorStateProps {
  message: string;
  onRetry: () => void;
  supportLine?: string;
}

export function ErrorState({ message, onRetry, supportLine }: ErrorStateProps) {
  return (
    <div className="flex flex-col items-center gap-3 rounded-lg border border-hairline bg-surface-sunken px-6 py-10 text-center">
      <AlertCircle className="h-6 w-6 text-danger/60" aria-hidden="true" />
      <p className="text-sm text-ink">{message}</p>
      <button
        type="button"
        onClick={onRetry}
        className="text-sm font-medium text-brand hover:underline"
      >
        Try again
      </button>
      {supportLine && (
        <p className="text-xs text-ink-muted">{supportLine}</p>
      )}
    </div>
  );
}
