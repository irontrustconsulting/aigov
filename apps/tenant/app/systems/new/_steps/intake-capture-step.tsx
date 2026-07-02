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

export interface IntakeCaptureStepProps {
  isCustom: boolean;
  // Wizard-state-controlled values (DM-S4a)
  name: string;
  operatorRoleId: string | null;
  hostingModelId: string | null;
  lifecycleStage: SystemLifecycleStage | null;
  purpose: string | null;
  prefillBases: IntakePrefillBases | null;
  onFieldChange: (field: IntakeFieldName, value: string | null) => void;
  onSubmit: () => void;
}

/**
 * WI-7 (DM-S2): system-stable capture — name, operator role, hosting model,
 * lifecycle stage, purpose. Fully wizard-state-controlled (DM-S4a): values
 * come from props, changes dispatch to the reducer; seeded fields render
 * FE-30 basis captions; a user edit clears the caption to user-set.
 */
export function IntakeCaptureStep({
  isCustom: _isCustom,
  name,
  operatorRoleId,
  hostingModelId,
  lifecycleStage,
  purpose,
  prefillBases,
  onFieldChange,
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

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    onSubmit();
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
          <BasisCaption basis={prefillBases?.operatorRoleId} />
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
          <BasisCaption basis={prefillBases?.lifecycleStage} />
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

        <Button type="submit">
          Continue
        </Button>
      </form>
    </PageScaffold>
  );
}
