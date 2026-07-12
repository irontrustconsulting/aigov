import { useState } from "react";
import { Button, SectionGroup, SingleSelect, type SelectOption } from "@irontrust/ui";
import type { IntakeFieldName } from "@/app/systems/new/wizard-state";

export interface DerivedDispositionItem {
  field: IntakeFieldName;
  label: string;
  value: string;
  options: SelectOption[];
  confirmed: boolean;
}

export interface PreCommitDispositionGateProps {
  derivedItems: DerivedDispositionItem[];
  onConfirm: (field: IntakeFieldName) => void;
  onChange: (field: IntakeFieldName, value: string) => void;
  factCount: number;
  onReviewFacts: () => void;
}

function DerivedItemRow({
  item,
  onConfirm,
  onChange,
}: {
  item: DerivedDispositionItem;
  onConfirm: (field: IntakeFieldName) => void;
  onChange: (field: IntakeFieldName, value: string) => void;
}) {
  const [revealed, setRevealed] = useState(false);

  if (revealed) {
    return (
      <div className="flex items-start justify-between gap-4 py-3 border-b border-hairline last:border-b-0">
        <div className="min-w-0 flex-1">
          <SingleSelect
            id={`disposition-${item.field}`}
            label={item.label}
            value={item.value}
            options={item.options}
            onChange={(v) => onChange(item.field, v)}
          />
        </div>
        <div className="flex-shrink-0">
          <Button type="button" variant="secondary" onClick={() => setRevealed(false)}>
            Change
          </Button>
        </div>
      </div>
    );
  }

  const displayValue = item.options.find((o) => o.value === item.value)?.label ?? item.value;

  return (
    <div className="flex items-start justify-between gap-4 py-3 border-b border-hairline last:border-b-0">
      <div className="min-w-0">
        <p className="font-medium text-ink">{item.label}</p>
        <p className="mt-0.5 text-ink">{displayValue}</p>
        {item.confirmed ? (
          <p className="mt-1 inline-flex items-center gap-1 text-xs text-ink-muted">
            <span className="inline-flex h-3.5 w-3.5 items-center justify-center rounded-full bg-brand text-[9px] text-surface">
              &#10003;
            </span>
            Derived, confirmed
          </p>
        ) : (
          <p className="mt-1 text-xs text-ink-muted">Derived, confirm or update</p>
        )}
      </div>
      <div className="flex flex-shrink-0 items-center gap-2">
        <Button type="button" variant="secondary" onClick={() => setRevealed(true)}>
          Change
        </Button>
        {!item.confirmed && (
          <Button type="button" variant="ghost" onClick={() => onConfirm(item.field)}>
            Confirm
          </Button>
        )}
      </div>
    </div>
  );
}

/**
 * FE-36 (E-compact, Path B): pre-commit disposition gate for derived intake
 * defaults left undispositioned on resume (INV-83 ALTER, FIX-RESUME-REGATE).
 * Hidden when every derived item is already confirmed. Facts recap is a
 * non-blocking nudge — an unreviewed fact keeps its catalogue-curated
 * provenance; it is never synthesised as confirmed (DF-RR-3).
 */
export function PreCommitDispositionGate({
  derivedItems,
  onConfirm,
  onChange,
  factCount,
  onReviewFacts,
}: PreCommitDispositionGateProps) {
  const hasUnconfirmed = derivedItems.some((item) => !item.confirmed);
  if (!hasUnconfirmed) return null;

  return (
    <SectionGroup title="Before you register">
      <p className="mb-3 text-xs text-ink-muted">
        These were prefilled from the catalogue and need your confirmation. Change any that are wrong.
      </p>
      <div>
        {derivedItems.map((item) => (
          <DerivedItemRow key={item.field} item={item} onConfirm={onConfirm} onChange={onChange} />
        ))}
      </div>
      {factCount > 0 && (
        <div className="mt-3.5 flex items-center justify-between gap-4 rounded-lg border border-hairline bg-surface-sunken p-3">
          <p className="text-sm text-ink">
            {factCount} catalogue facts have not been reviewed this session.{" "}
            <span className="text-ink-muted">They will be kept as recorded in the catalogue unless you review them.</span>
          </p>
          <button
            type="button"
            onClick={onReviewFacts}
            className="whitespace-nowrap text-sm font-medium text-brand hover:underline"
          >
            Review facts &#8250;
          </button>
        </div>
      )}
    </SectionGroup>
  );
}
