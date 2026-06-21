"use client";

import { useState } from "react";
import { Button, FreeText, MultiSelectInput, SingleSelect, type SelectOption } from "@irontrust/ui";
import type { SystemCreate, SystemDetail, SystemLifecycleStage } from "@irontrust/api-client";
import {
  useAffectedParties,
  useCreateSystem,
  useDataCategories,
  useHostingModels,
  useHumanOversightTypes,
  useOperatorRoles,
  useUsageContexts,
} from "@/lib/intake";

const LIFECYCLE_STAGE_OPTIONS: SelectOption[] = [
  { value: "development", label: "Development" },
  { value: "pilot", label: "Pilot" },
  { value: "production", label: "Production" },
  { value: "retired", label: "Retired" },
];

export interface IntakeCaptureStepProps {
  isCustom: boolean;
  catalogueProductId: string | null;
  onSubmit: (system: SystemDetail) => void;
}

/**
 * WI-5: structured capture (FE-4) — four single-selects, two multi-selects,
 * lifecycle_stage, and `purpose` as the contained last-resort free text.
 * Mirrors the server's `is_custom XOR catalogue_product_id` guard
 * structurally — when WI-4 set is_custom, the catalogue fields are never
 * part of the payload at all, not merely hidden.
 */
export function IntakeCaptureStep({ isCustom, catalogueProductId, onSubmit }: IntakeCaptureStepProps) {
  const [name, setName] = useState("");
  const [operatorRoleId, setOperatorRoleId] = useState("");
  const [hostingModelId, setHostingModelId] = useState("");
  const [usageContextId, setUsageContextId] = useState("");
  const [humanOversightTypeId, setHumanOversightTypeId] = useState("");
  const [lifecycleStage, setLifecycleStage] = useState<SystemLifecycleStage | "">("");
  const [dataCategoryIds, setDataCategoryIds] = useState<string[]>([]);
  const [affectedPartyIds, setAffectedPartyIds] = useState<string[]>([]);
  const [purpose, setPurpose] = useState("");

  const operatorRoles = useOperatorRoles();
  const hostingModels = useHostingModels();
  const usageContexts = useUsageContexts();
  const humanOversightTypes = useHumanOversightTypes();
  const dataCategories = useDataCategories();
  const affectedParties = useAffectedParties();

  const createSystem = useCreateSystem();

  function toOptions(items: { id: string; label: string }[] | undefined): SelectOption[] {
    return (items ?? []).map((i) => ({ value: i.id, label: i.label }));
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const body: SystemCreate = {
      name,
      is_custom: isCustom,
      // Structurally XOR with is_custom — never both populated (mirrors the
      // server's ck_system_custom_no_catalogue guard, client-side).
      catalogue_product_id: isCustom ? null : catalogueProductId,
      catalogue_vendor_id: null, // server derives this from the product
      owner_user_id: null,
      operator_role_id: operatorRoleId || null,
      hosting_model_id: hostingModelId || null,
      usage_context_id: usageContextId || null,
      human_oversight_type_id: humanOversightTypeId || null,
      lifecycle_stage: lifecycleStage || null,
      data_category_ids: dataCategoryIds,
      affected_party_ids: affectedPartyIds,
      purpose: purpose || null,
    };
    createSystem.mutate(body, { onSuccess: onSubmit });
  }

  return (
    <form aria-label="intake-capture" onSubmit={handleSubmit}>
      <div>
        <label htmlFor="system-name">System name</label>
        <input id="system-name" value={name} onChange={(e) => setName(e.target.value)} required />
      </div>

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
        id="usage-context"
        label="Usage context"
        value={usageContextId}
        options={toOptions(usageContexts.data)}
        onChange={setUsageContextId}
      />
      <SingleSelect
        id="human-oversight-type"
        label="Human oversight"
        value={humanOversightTypeId}
        options={toOptions(humanOversightTypes.data)}
        onChange={setHumanOversightTypeId}
      />
      <SingleSelect
        id="lifecycle-stage"
        label="Lifecycle stage"
        value={lifecycleStage}
        options={LIFECYCLE_STAGE_OPTIONS}
        onChange={(v) => setLifecycleStage(v as SystemLifecycleStage)}
      />

      <MultiSelectInput
        id="data-categories"
        label="Data categories"
        values={dataCategoryIds}
        options={toOptions(dataCategories.data)}
        onChange={setDataCategoryIds}
      />
      <MultiSelectInput
        id="affected-parties"
        label="Affected parties"
        values={affectedPartyIds}
        options={toOptions(affectedParties.data)}
        onChange={setAffectedPartyIds}
      />

      <FreeText id="purpose" label="Purpose (optional)" value={purpose} onChange={setPurpose} />

      {createSystem.isError && <p role="alert">Could not register this system. Check the form and try again.</p>}

      <Button type="submit" disabled={createSystem.isPending}>
        Continue
      </Button>
    </form>
  );
}
