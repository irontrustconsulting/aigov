import type { SelectOption } from "./single-select";

/** FE-4: multi-select rung of the input-preference order. */
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
    <fieldset id={id}>
      <legend>{label}</legend>
      {options.map((opt) => (
        <label key={opt.value}>
          <input
            type="checkbox"
            checked={values.includes(opt.value)}
            onChange={() => toggle(opt.value)}
          />
          {opt.label}
        </label>
      ))}
    </fieldset>
  );
}
