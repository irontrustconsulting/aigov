"use client";

import { useState } from "react";
import { Button, MultiSelectInput, PageHeader, PageScaffold, SingleSelect, Skeleton, ErrorState, type SelectOption } from "@irontrust/ui";
import type { RegistrationRead, SystemLifecycleStage } from "@irontrust/api-client";
import {
  useAffectedParties,
  useDataCategories,
  useHumanOversightTypes,
  useProductCategoryMemberships,
  useRegister,
  useUsageContexts,
} from "@/lib/intake";

export interface UseCaseCreateStepProps {
  // System-stable facts from wizard state (captured at intake step)
  name: string;
  isCustom: boolean;
  catalogueProductId: string | null;
  operatorRoleId: string | null;
  hostingModelId: string | null;
  lifecycleStage: SystemLifecycleStage | null;
  purpose: string | null;
  /** DM-S3: when set, the draft is atomically discarded on successful registration (D-66). */
  draftId: string | null;
  onCreated: (
    result: RegistrationRead,
    context: {
      usageContextId: string | null;
      humanOversightTypeId: string | null;
      dataCategoryIds: string[];
      affectedPartyIds: string[];
    }
  ) => void;
}

const OTHER_OPTION_VALUE = "__other__";

/**
 * WI-9 (DM-S2): POST /v1/registrations — the atomic boundary. System-stable
 * facts come from wizard state (props); use-distinguishing context is
 * captured here (DF-D2-1, closes DF-D1-2). The branch on the response
 * (requires_context / prohibited / resolved) is encoded once, in the
 * wizard reducer — this component only creates and hands the result up.
 *
 * FE-31: intended-use category replaces free-text purpose. Membership-
 * constrained SingleSelect for catalogue products; custom systems present
 * only "Other / not listed" (no product → no memberships).
 */
export function UseCaseCreateStep({
  name,
  isCustom,
  catalogueProductId,
  operatorRoleId,
  hostingModelId,
  lifecycleStage,
  purpose,
  draftId,
  onCreated,
}: UseCaseCreateStepProps) {
  const [title, setTitle] = useState("");
  const [intendedUseCategoryId, setIntendedUseCategoryId] = useState("");
  const [usageContextId, setUsageContextId] = useState("");
  const [humanOversightTypeId, setHumanOversightTypeId] = useState("");
  const [dataCategoryIds, setDataCategoryIds] = useState<string[]>([]);
  const [affectedPartyIds, setAffectedPartyIds] = useState<string[]>([]);

  const categoryMemberships = useProductCategoryMemberships(catalogueProductId);
  const usageContexts = useUsageContexts();
  const humanOversightTypes = useHumanOversightTypes();
  const dataCategories = useDataCategories();
  const affectedParties = useAffectedParties();
  const register = useRegister();

  const vocabQueries = [usageContexts, humanOversightTypes, dataCategories, affectedParties];
  const isLoading = vocabQueries.some((q) => q.isLoading) || categoryMemberships.isLoading;
  const isError = vocabQueries.some((q) => q.isError) || categoryMemberships.isError;

  if (isLoading) return <Skeleton />;
  if (isError) {
    const errorQueries = [...vocabQueries, categoryMemberships].filter((q) => q.isError);
    return (
      <PageScaffold>
        <PageHeader title="Describe your use case" />
        <ErrorState
          message="Could not load form options."
          onRetry={() => errorQueries.forEach((q) => q.refetch())}
        />
      </PageScaffold>
    );
  }

  function toOptions(items: { id: string; label: string }[] | undefined): SelectOption[] {
    return (items ?? []).map((i) => ({ value: i.id, label: i.label }));
  }

  const categoryOptions: SelectOption[] = [
    ...(categoryMemberships.data ?? []).map((c) => ({ value: c.id, label: c.name })),
    { value: OTHER_OPTION_VALUE, label: "Other / not listed" },
  ];

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const selectedCategoryId =
      intendedUseCategoryId && intendedUseCategoryId !== OTHER_OPTION_VALUE
        ? intendedUseCategoryId
        : null;

    register.mutate(
      {
        // system-stable (from wizard state)
        name,
        is_custom: isCustom,
        catalogue_product_id: isCustom ? null : catalogueProductId,
        operator_role_id: operatorRoleId,
        hosting_model_id: hostingModelId,
        lifecycle_stage: lifecycleStage,
        owner_user_id: null,
        purpose,
        // first use case (local state)
        title,
        intended_use_category_id: selectedCategoryId,
        context_blob: {},
        usage_context_id: usageContextId || null,
        human_oversight_type_id: humanOversightTypeId || null,
        data_category_ids: dataCategoryIds,
        affected_party_ids: affectedPartyIds,
        // DM-S3: discard draft atomically on success (D-66)
        draft_id: draftId ?? undefined,
      },
      {
        onSuccess: (data: RegistrationRead) =>
          onCreated(data, {
            usageContextId: usageContextId || null,
            humanOversightTypeId: humanOversightTypeId || null,
            dataCategoryIds,
            affectedPartyIds,
          }),
      }
    );
  }

  return (
    <PageScaffold>
      <PageHeader title="Describe your use case" />
      <form aria-label="use-case-create" onSubmit={handleSubmit} className="border-hairline space-y-4 rounded-lg border p-4">
        <div className="space-y-1">
          <label htmlFor="use-case-title" className="text-sm font-medium">What are you using this for?</label>
          <input id="use-case-title" value={title} onChange={(e) => setTitle(e.target.value)} required className="border-hairline w-full rounded border px-3 py-1.5 text-sm" />
        </div>

        <SingleSelect
          id="intended-use-category"
          label="Intended-use category"
          value={intendedUseCategoryId}
          options={categoryOptions}
          onChange={setIntendedUseCategoryId}
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

        {register.isError && (
          <div role="alert" className="text-sm text-danger">Could not register this system and use case. Check the form and try again.</div>
        )}

        <Button type="submit" disabled={register.isPending}>
          Continue
        </Button>
      </form>
    </PageScaffold>
  );
}
