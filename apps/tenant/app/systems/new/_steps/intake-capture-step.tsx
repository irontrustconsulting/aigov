"use client";

import { useState } from "react";
import { Button, ErrorState, FreeText, PageHeader, PageScaffold, SingleSelect, Skeleton, TextInput, type SelectOption } from "@irontrust/ui";
import type { SystemLifecycleStage } from "@irontrust/api-client";
import {
  useHostingModels,
  useOperatorRoles,
} from "@/lib/intake";

const LIFECYCLE_STAGE_OPTIONS: SelectOption[] = [
  { value: "development", label: "Development" },
  { value: "pilot", label: "Pilot" },
  { value: "production", label: "Production" },
  { value: "retired", label: "Retired" },
];

export interface IntakeCaptureFacts {
  name: string;
  operatorRoleId: string | null;
  hostingModelId: string | null;
  lifecycleStage: SystemLifecycleStage | null;
  purpose: string | null;
}

export interface IntakeCaptureStepProps {
  isCustom: boolean;
  catalogueProductId: string | null;
  onSubmit: (facts: IntakeCaptureFacts) => void;
}

/**
 * WI-7 (DM-S2): system-stable capture only — name, operator role, hosting
 * model, lifecycle stage, purpose. No network call here; facts are held in
 * wizard state and sent with the use-case facts in POST /v1/registrations
 * at the use-case step (DF-D2-3). The four use-distinguishing context
 * controls moved to use-case-create-step (DF-D2-1, closes DF-D1-2).
 */
export function IntakeCaptureStep({ isCustom, catalogueProductId, onSubmit }: IntakeCaptureStepProps) {
  const [name, setName] = useState("");
  const [operatorRoleId, setOperatorRoleId] = useState("");
  const [hostingModelId, setHostingModelId] = useState("");
  const [lifecycleStage, setLifecycleStage] = useState<SystemLifecycleStage | "">("");
  const [purpose, setPurpose] = useState("");

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
    onSubmit({
      name,
      operatorRoleId: operatorRoleId || null,
      hostingModelId: hostingModelId || null,
      lifecycleStage: (lifecycleStage || null) as SystemLifecycleStage | null,
      purpose: purpose || null,
    });
  }

  return (
    <PageScaffold>
      <PageHeader title="Register a system" />
      <form aria-label="intake-capture" onSubmit={handleSubmit} className="border-hairline space-y-4 rounded-lg border p-4">
        <TextInput id="system-name" label="System name" value={name} onChange={setName} />

        <SingleSelect
          id="operator-role"
          label="Operator role"
          value={operatorRoleId}
          options={toOptions(operatorRoles.data)}
          onChange={setOperatorRoleId}
        />
        <SingleSelect
          id="hosting-model"
          label="Hosting model"
          value={hostingModelId}
          options={toOptions(hostingModels.data)}
          onChange={setHostingModelId}
        />
        <SingleSelect
          id="lifecycle-stage"
          label="Lifecycle stage"
          value={lifecycleStage}
          options={LIFECYCLE_STAGE_OPTIONS}
          onChange={(v) => setLifecycleStage(v as SystemLifecycleStage)}
        />

        <FreeText id="purpose" label="Purpose (optional)" value={purpose} onChange={setPurpose} />

        <Button type="submit">
          Continue
        </Button>
      </form>
    </PageScaffold>
  );
}
