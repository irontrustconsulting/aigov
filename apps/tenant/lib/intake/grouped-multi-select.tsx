import { MultiSelectInput } from "@irontrust/ui";

export interface GroupedMultiSelectOption {
  value: string;
  label: string;
  group: "duty" | "other";
}

export interface GroupedMultiSelectProps {
  id: string;
  label: string;
  values: string[];
  options: GroupedMultiSelectOption[];
  onChange: (next: string[]) => void;
  dutyHeading: string;
  dutyCaption: string;
  otherHeading: string;
}

/**
 * FE-34: partitions a vocab multiselect into a heightened-duty subgroup and
 * an "other" subgroup, sharing one selection array. Neutral hairline rule
 * on the duty subgroup — no --verdict-*, no brand. Tenant-local (DF-UC-4);
 * precedent locus fact-value.tsx (INV-84).
 */
export function GroupedMultiSelect({
  id,
  label,
  values,
  options,
  onChange,
  dutyHeading,
  dutyCaption,
  otherHeading,
}: GroupedMultiSelectProps) {
  const dutyOptions = options.filter((o) => o.group === "duty");
  const otherOptions = options.filter((o) => o.group === "other");

  return (
    <div id={id} className="space-y-3">
      <span className="text-sm font-medium text-ink">{label}</span>
      {dutyOptions.length > 0 && (
        <div className="border-l-2 border-hairline-strong pl-3 space-y-2">
          <div className="flex items-baseline gap-2">
            <span className="text-xs font-semibold text-ink">{dutyHeading}</span>
            <span className="text-xs text-ink-muted">{dutyCaption}</span>
          </div>
          <MultiSelectInput
            id={`${id}-duty`}
            label={dutyHeading}
            hideLabel
            values={values}
            options={dutyOptions}
            onChange={onChange}
          />
        </div>
      )}
      {otherOptions.length > 0 && (
        <div className="pl-3.5 space-y-2">
          <p className="text-xs font-semibold text-ink">{otherHeading}</p>
          <MultiSelectInput
            id={`${id}-other`}
            label={otherHeading}
            hideLabel
            values={values}
            options={otherOptions}
            onChange={onChange}
          />
        </div>
      )}
    </div>
  );
}
