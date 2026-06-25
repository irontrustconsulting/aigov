import { ChevronRight } from "lucide-react";

export interface ListSelectRowProps {
  label: string;
  onClick: () => void;
  disabled?: boolean;
  leading?: React.ReactNode;
}

/** ListSelectRow (FE-23) — whole-row selectable item with optional leading slot and trailing chevron. */
export function ListSelectRow({ label, onClick, disabled, leading }: ListSelectRowProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className="flex w-full items-center justify-between rounded-md border border-hairline bg-surface px-4 py-3 text-left text-sm font-medium text-ink transition-colors hover:bg-surface-sunken disabled:cursor-not-allowed disabled:opacity-50"
    >
      <span className="flex items-center gap-3">
        {leading}
        {label}
      </span>
      <ChevronRight className="h-4 w-4 shrink-0 text-ink-muted" aria-hidden="true" />
    </button>
  );
}
