export interface SelectOption {
  value: string;
  label: string;
}

/** FE-4 (ALTER INV-81): select-first, realising UX-2/UX-3 — a native select for now (the
 * Radix-based richer variant lands per-surface as needed); the contract
 * (structured, enumerable choice) is what F0 fixes. Always renders a leading
 * non-selectable placeholder so the displayed value equals the bound state. */
export function SingleSelect({
  id,
  label,
  value,
  options,
  onChange,
  placeholder = "Select…",
}: {
  id: string;
  label: string;
  value: string;
  options: SelectOption[];
  onChange: (value: string) => void;
  placeholder?: string;
}) {
  return (
    <div className="space-y-1">
      <label htmlFor={id} className="block text-sm font-medium text-ink">
        {label}
      </label>
      <select
        id={id}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="block w-full appearance-none rounded border border-hairline bg-surface bg-[url('data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTIiIGhlaWdodD0iOCIgdmlld0JveD0iMCAwIDEyIDgiIGZpbGw9Im5vbmUiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PHBhdGggZD0iTTEgMUw2IDdMMTEgMSIgc3Ryb2tlPSIjNkI3MjgwIiBzdHJva2Utd2lkdGg9IjEuNSIgc3Ryb2tlLWxpbmVjYXA9InJvdW5kIiBzdHJva2UtbGluZWpvaW49InJvdW5kIi8+PC9zdmc+')] bg-[length:12px_8px] bg-[position:right_12px_center] bg-no-repeat px-3 py-1.5 pr-8 text-sm text-ink focus:outline-none focus:ring-1 focus:ring-ink/20"
      >
        <option value="" disabled hidden>{placeholder}</option>
        {options.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>
    </div>
  );
}
