interface Props {
  label?: string;
}

/**
 * INV-51/52 / DF6-8: hard visual boundary between interactive coverage and
 * audit-grade coverage (or around include_unapproved views). Required wherever
 * the two grades could co-render.
 */
export function AuditGradeDivider({
  label = "Audit-grade coverage below — generated on deliberate action",
}: Props) {
  return (
    <div
      role="region"
      aria-label="audit-grade-divider"
      className="border-hairline-strong bg-surface-sunken my-4 flex items-center gap-3 rounded border px-4 py-2"
    >
      <div className="bg-hairline-strong h-px flex-1" />
      <span className="text-ink-muted text-xs font-semibold uppercase tracking-wide">
        {label}
      </span>
      <div className="bg-hairline-strong h-px flex-1" />
    </div>
  );
}
