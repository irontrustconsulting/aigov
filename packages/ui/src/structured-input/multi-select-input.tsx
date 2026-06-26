import type { SelectOption } from "./single-select";

/** FE-4: multi-select rung of the input-preference order.
 *  Renders as a spaced wrapping toggle-chip cluster (INV-73 — neutral selection token). */
export function MultiSelectInput({
  id,
  label,
  values,
  options,
  onChange,
}: {
  id: string;
  label: string;
  values: string[];
  options: SelectOption[];
  onChange: (values: string[]) => void;
}) {
  function toggle(value: string) {
    onChange(values.includes(value) ? values.filter((v) => v !== value) : [...values, value]);
  }

  return (
    <fieldset id={id} className="space-y-2">
      <legend className="text-sm font-medium text-ink">{label}</legend>
      <div className="flex flex-wrap gap-2">
        {options.map((opt) => {
          const checked = values.includes(opt.value);
          return (
            <label
              key={opt.value}
              className={`inline-flex cursor-pointer items-center rounded-full border px-3 py-1 text-sm font-medium transition-colors ${
                checked
                  ? "border-ink bg-ink text-surface"
                  : "border-hairline bg-surface text-ink hover:bg-surface-sunken"
              }`}
            >
              <input
                type="checkbox"
                checked={checked}
                onChange={() => toggle(opt.value)}
                className="sr-only"
              />
              {opt.label}
            </label>
          );
        })}
      </div>
    </fieldset>
  );
}
