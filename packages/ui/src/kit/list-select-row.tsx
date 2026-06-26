import { ChevronRight } from "lucide-react";

export interface ListSelectRowProps {
  label: string;
  onClick: () => void;
  disabled?: boolean;
  leading?: React.ReactNode;
  /** Branch mode (FE-23 ALTER) — all optional; leaf mode is the default when omitted. */
  onToggle?: () => void;
  expanded?: boolean;
  children?: React.ReactNode;
}

/** ListSelectRow (FE-23) — whole-row selectable item with optional leading slot and trailing chevron.
 *  Pass onToggle/expanded/children to use disclosure (branch) mode; leaf mode is the default. */
export function ListSelectRow({ label, onClick, disabled, leading, onToggle, expanded, children }: ListSelectRowProps) {
  const isBranch = onToggle !== undefined;
  const handleClick = isBranch ? onToggle : onClick;

  const button = (
    <button
      type="button"
      onClick={handleClick}
      disabled={disabled}
      aria-expanded={isBranch ? expanded : undefined}
      className="flex w-full items-center justify-between rounded-md border border-hairline bg-surface px-4 py-3 text-left text-sm font-medium text-ink transition-colors hover:bg-surface-sunken disabled:cursor-not-allowed disabled:opacity-50"
    >
      <span className="flex items-center gap-3">
        {leading}
        {label}
      </span>
      <ChevronRight
        className={`h-4 w-4 shrink-0 text-ink-muted transition-transform${isBranch && expanded ? " rotate-90" : ""}`}
        aria-hidden="true"
      />
    </button>
  );

  if (!isBranch) return button;

  return (
    <div>
      {button}
      {expanded && children ? <div>{children}</div> : null}
    </div>
  );
}
