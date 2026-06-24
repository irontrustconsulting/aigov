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
  if (isYourCourt) {
    return (
      <span
        data-court="yours"
        className="inline-flex items-center px-2 py-1 text-xs font-medium"
        style={{
          borderLeft: "3px solid var(--color-brand)",
          borderRadius: "0 var(--radius-sm) var(--radius-sm) 0",
          backgroundColor: "var(--color-brand-tint)",
          color: "var(--color-brand-strong)",
        }}
      >
        {partyLabel}
      </span>
    );
  }
  return (
    <span
      data-court="theirs"
      className="inline-flex items-center rounded-sm border border-hairline bg-surface-sunken px-2 py-1 text-xs text-ink-muted"
    >
      {partyLabel}
    </span>
  );
}
