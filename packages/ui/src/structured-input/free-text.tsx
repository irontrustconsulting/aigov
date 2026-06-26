/** FE-4: contained free-text — last resort in the input-preference order,
 * visually de-emphasized per UX-2/UX-3, used only when no structured shape fits. */
export function FreeText({
  id,
  label,
  value,
  onChange,
  hint,
}: {
  id: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  /** Last-resort hint shown below the field (muted). */
  hint?: string;
}) {
  return (
    <div className="space-y-1">
      <label htmlFor={id} className="block text-sm font-medium text-ink-muted">
        {label}
      </label>
      <textarea
        id={id}
        rows={3}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="block w-full rounded border border-hairline bg-surface px-3 py-1.5 text-sm text-ink-muted placeholder:text-ink-muted/50 focus:outline-none focus:ring-1 focus:ring-ink/20"
      />
      {hint && <p className="text-xs text-ink-muted">{hint}</p>}
    </div>
  );
}
