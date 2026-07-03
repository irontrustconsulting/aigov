"use client";

import { Button, ErrorState, FreeText, PageHeader, PageScaffold, SingleSelect, Skeleton, TextInput, type SelectOption } from "@irontrust/ui";
import type { SystemLifecycleStage } from "@irontrust/api-client";
import {
  useHostingModels,
  useOperatorRoles,
} from "@/lib/intake";
import type { IntakeFieldBasis, IntakeFieldName, IntakePrefillBases } from "../wizard-state";

const LIFECYCLE_STAGE_OPTIONS: SelectOption[] = [
  { value: "development", label: "Development" },
  { value: "pilot", label: "Pilot" },
  { value: "production", label: "Production" },
  { value: "retired", label: "Retired" },
];

const BASIS_LABELS: Record<Exclude<IntakeFieldBasis, "user-set">, string> = {
  catalogue: "Catalogue curated — confirm or update",
  derived: "Derived — confirm or update",
};

function BasisCaption({ basis }: { basis: IntakeFieldBasis | undefined }) {
  if (!basis || basis === "user-set") return null;
  return <p className="text-xs text-ink-muted">{BASIS_LABELS[basis]}</p>;
}

/** FE-32: confirm affordance for a derived field. Shows a confirm button when
 * unconfirmed; shows a confirmed indicator once the user has confirmed. */
function DerivedConfirmControl({
  isConfirmed,
  onConfirm,
}: {
  isConfirmed: boolean;
  onConfirm: () => void;
}) {
  if (isConfirmed) {
    return <p className="text-xs text-ink-muted">Derived — confirmed</p>;
  }
  return (
    <div className="flex items-center gap-2">
      <p className="text-xs text-ink-muted">Derived — confirm or update</p>
      <Button type="button" variant="ghost" className="px-2 py-1 text-xs" onClick={onConfirm}>
        Confirm
      </Button>
    </div>
  );
}

export interface IntakeCaptureStepProps {
  isCustom: boolean;
  // Wizard-state-controlled values (DM-S4a)
  name: string;
  operatorRoleId: string | null;
  hostingModelId: string | null;
  lifecycleStage: SystemLifecycleStage | null;
  purpose: string | null;
  prefillBases: IntakePrefillBases | null;
  // FE-32: confirmed derived fields (camelCase UI names); used to gate Continue.
  confirmedIntakeFields: string[];
  onFieldChange: (field: IntakeFieldName, value: string | null) => void;
  onConfirmField: (field: IntakeFieldName) => void;
  onSubmit: () => void;
}

/**
 * WI-7 (DM-S2): system-stable capture — name, operator role, hosting model,
 * lifecycle stage, purpose. Fully wizard-state-controlled (DM-S4a): values
 * come from props, changes dispatch to the reducer; seeded fields render
 * FE-30 basis captions (catalogue) or FE-32 confirm controls (derived);
 * a user edit clears the caption to user-set.
 *
 * FE-32: Continue is gated until every derived field is dispositioned
 * (confirmed or edited). Catalogue-seeded fields take submit-as-confirmation.
 */
export function IntakeCaptureStep({
  isCustom: _isCustom,
  name,
  operatorRoleId,
  hostingModelId,
  lifecycleStage,
  purpose,
  prefillBases,
  confirmedIntakeFields,
  onFieldChange,
  onConfirmField,
  onSubmit,
}: IntakeCaptureStepProps) {
  const operatorRoles = useOperatorRoles();
  const hostingModels = useHostingModels();

  const vocabQueries = [operatorRoles, hostingModels];
  if (vocabQueries.some((q) => q.isLoading)) return <Skeleton />;
  if (vocabQueries.some((q) => q.isError)) {
    return (
      <PageScaffold>
        <PageHeader title="Register a system" />
        <ErrorState
          message="Could not load form options."
          onRetry={() => vocabQueries.filter((q) => q.isError).forEach((q) => q.refetch())}
        />
      </PageScaffold>
    );
  }

  function toOptions(items: { id: string; label: string }[] | undefined): SelectOption[] {
    return (items ?? []).map((i) => ({ value: i.id, label: i.label }));
  }

  // FE-32: Continue is disabled until every derived field is dispositioned.
  // A derived field is dispositioned when: confirmed (in confirmedIntakeFields)
  // OR its basis is "user-set" (edited to differ from seed → server derives USER_AMENDED).
  const derivedUnconfirmed: IntakeFieldName[] = (
    [
      ["operatorRoleId", prefillBases?.operatorRoleId],
      ["lifecycleStage", prefillBases?.lifecycleStage],
    ] as [IntakeFieldName, IntakeFieldBasis | undefined][]
  ).filter(
    ([field, basis]) => basis === "derived" && !confirmedIntakeFields.includes(field)
  ).map(([field]) => field);

  const canContinue = derivedUnconfirmed.length === 0;

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (canContinue) onSubmit();
  }

  return (
    <PageScaffold>
      <PageHeader title="Register a system" />
      <form aria-label="intake-capture" onSubmit={handleSubmit} className="border-hairline space-y-4 rounded-lg border p-4">
        <TextInput
          id="system-name"
          label="System name"
          value={name}
          onChange={(v) => onFieldChange("name", v)}
        />

        <div className="space-y-1">
          <SingleSelect
            id="operator-role"
            label="Operator role"
            value={operatorRoleId ?? ""}
            options={toOptions(operatorRoles.data)}
            onChange={(v) => onFieldChange("operatorRoleId", v || null)}
          />
          {prefillBases?.operatorRoleId === "derived" ? (
            <DerivedConfirmControl
              isConfirmed={confirmedIntakeFields.includes("operatorRoleId")}
              onConfirm={() => onConfirmField("operatorRoleId")}
            />
          ) : (
            <BasisCaption basis={prefillBases?.operatorRoleId} />
          )}
        </div>

        <div className="space-y-1">
          <SingleSelect
            id="hosting-model"
            label="Hosting model"
            value={hostingModelId ?? ""}
            options={toOptions(hostingModels.data)}
            onChange={(v) => onFieldChange("hostingModelId", v || null)}
          />
          <BasisCaption basis={prefillBases?.hostingModelId} />
        </div>

        <div className="space-y-1">
          <SingleSelect
            id="lifecycle-stage"
            label="Lifecycle stage"
            value={lifecycleStage ?? ""}
            options={LIFECYCLE_STAGE_OPTIONS}
            onChange={(v) => onFieldChange("lifecycleStage", v || null)}
          />
          {prefillBases?.lifecycleStage === "derived" ? (
            <DerivedConfirmControl
              isConfirmed={confirmedIntakeFields.includes("lifecycleStage")}
              onConfirm={() => onConfirmField("lifecycleStage")}
            />
          ) : (
            <BasisCaption basis={prefillBases?.lifecycleStage} />
          )}
        </div>

        <div className="space-y-1">
          <FreeText
            id="purpose"
            label="Purpose (optional)"
            value={purpose ?? ""}
            onChange={(v) => onFieldChange("purpose", v || null)}
          />
          <BasisCaption basis={prefillBases?.purpose} />
        </div>

        <Button type="submit" disabled={!canContinue}>
          Continue
        </Button>
      </form>
    </PageScaffold>
  );
}
