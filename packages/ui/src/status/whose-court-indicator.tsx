/**
 * UX.md §5 "whose-court" status indicator. Promoted from the F0 generic
 * pill to real semantics by UI-F2-PORTFOLIO (FE-11): bound to a resolved
 * party label and whether it's the caller's own court
 * (`apps/tenant/lib/portfolio/court.ts`). Presentational only — the
 * highlight is a visual correlate of the server-authoritative role match
 * (FE-8, D-24); it never decides authorisation itself.
 */
export function WhoseCourtIndicator({
  partyLabel,
  isYourCourt,
}: {
  partyLabel: string;
  isYourCourt: boolean;
}) {
  return (
    <span
      className={
        isYourCourt
          ? "bg-accent text-bg border-accent inline-flex items-center rounded-sm border px-2 py-1 text-xs font-medium"
          : "bg-surface text-text border-border inline-flex items-center rounded-sm border px-2 py-1 text-xs"
      }
    >
      {partyLabel}
    </span>
  );
}
