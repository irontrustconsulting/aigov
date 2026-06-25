import { ChevronRight } from "lucide-react";

export interface ListSelectRowProps {
  label: string;
  onClick: () => void;
  disabled?: boolean;
}

/** ListSelectRow — whole-row selectable item with a single trailing chevron.
 *  No per-row action label (sprint WI-5 / f1_category_select_professional_target). */
export function ListSelectRow({ label, onClick, disabled }: ListSelectRowProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className="flex w-full items-center justify-between rounded-md border border-hairline bg-surface px-4 py-3 text-left text-sm font-medium text-ink transition-colors hover:bg-surface-sunken disabled:cursor-not-allowed disabled:opacity-50"
    >
      <span>{label}</span>
      <ChevronRight className="h-4 w-4 shrink-0 text-ink-muted" aria-hidden="true" />
    </button>
  );
}
