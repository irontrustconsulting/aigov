/**
 * UX.md §5 "whose-court" status indicator — scaffold only. A generic
 * labelled-state pill; real per-surface semantics (which states exist, what
 * each means) are filled in just-in-time against the first feature surface
 * that needs it, per UX.md §5's framing. Not a F0 feature surface.
 */
export function WhoseCourtIndicator({ label }: { label: string }) {
  return (
    <span className="bg-surface text-text border-border inline-flex items-center rounded-sm border px-2 py-1 text-xs">
      {label}
    </span>
  );
}
