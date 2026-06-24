/** FE-4: contained free-text — last resort in the input-preference order,
 * visually de-emphasized per UX-2/UX-3, used only when no structured shape
 * fits. */
export function FreeText({
  id,
  label,
  value,
  onChange,
}: {
  id: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <div>
      <label htmlFor={id}>{label}</label>
      <textarea
        id={id}
        className="text-ink-muted"
        value={value}
        onChange={(e) => onChange(e.target.value)}
      />
    </div>
  );
}
