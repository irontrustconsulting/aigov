export interface SelectOption {
  value: string;
  label: string;
}

/** FE-4: select-first, realising UX-2/UX-3 — a native select for now (the
 * Radix-based richer variant lands per-surface as needed); the contract
 * (structured, enumerable choice) is what F0 fixes. */
export function SingleSelect({
  id,
  label,
  value,
  options,
  onChange,
}: {
  id: string;
  label: string;
  value: string;
  options: SelectOption[];
  onChange: (value: string) => void;
}) {
  return (
    <div>
      <label htmlFor={id}>{label}</label>
      <select id={id} value={value} onChange={(e) => onChange(e.target.value)}>
        {options.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>
    </div>
  );
}
