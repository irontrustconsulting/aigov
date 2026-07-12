"use client";

import { useState } from "react";
import { Button, PageHeader, PageScaffold, SectionGroup, SingleSelect, Skeleton, ErrorState, TextInput, type SelectOption } from "@irontrust/ui";
import type { RegistrationRead, SystemLifecycleStage } from "@irontrust/api-client";
import {
  derivedUnconfirmed,
  GroupedMultiSelect,
  LIFECYCLE_STAGE_OPTIONS,
  PreCommitDispositionGate,
  useAffectedParties,
  useDataCategories,
  useHumanOversightTypes,
  useOperatorRoles,
  usePrefill,
  useProductCategoryMemberships,
  useRegister,
  useUsageContexts,
  type DerivedDispositionItem,
} from "@/lib/intake";
import type { IntakeFieldName, IntakePrefillBases } from "../wizard-state";

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
  /** FE-32/INV-83: camelCase UI keys for explicitly confirmed derived intake fields.
   * Converted to API snake_case at payload time. */
  confirmedIntakeFields: string[];
  /** WI-6: raw fact.key values confirmed as-is in the prefill step (USER_CONFIRMED). */
  confirmedFactKeys: string[];
  /** WI-6: raw fact.key values overridden in the prefill step (USER_AMENDED). */
  amendedFactKeys: string[];
  /** FIX-RESUME-REGATE (INV-83 ALTER): basis per seeded intake field, re-derived
   * value-vs-seed so a resume-restored derived default re-gates correctly. */
  intakePrefillBases: IntakePrefillBases | null;
  /** FE-36: confirm/change wiring for the pre-commit disposition gate — same
   * actions IntakeCaptureStep dispatches (CONFIRM_INTAKE_FIELD / SET_INTAKE_FIELD). */
  onConfirmField: (field: IntakeFieldName) => void;
  onFieldChange: (field: IntakeFieldName, value: string | null) => void;
  /** FE-36: Review-facts link target — navigates back to the prefill step. */
  onReviewFacts: () => void;
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
/** Map UI camelCase intake field names to API snake_case keys (D-74). */
const INTAKE_FIELD_API_KEY: Record<string, string> = {
  operatorRoleId: "operator_role_id",
  lifecycleStage: "lifecycle_stage",
  hostingModelId: "hosting_model_id",
  purpose: "purpose",
  name: "name",
};

export function UseCaseCreateStep({
  name,
  isCustom,
  catalogueProductId,
  operatorRoleId,
  hostingModelId,
  lifecycleStage,
  purpose,
  draftId,
  confirmedIntakeFields,
  confirmedFactKeys,
  amendedFactKeys,
  intakePrefillBases,
  onConfirmField,
  onFieldChange,
  onReviewFacts,
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
  const operatorRoles = useOperatorRoles();
  // V1 (FIX-RESUME-REGATE): cache-shared with page.tsx's usePrefill(state.catalogueProductId) —
  // same query key, no duplicate fetch. Used for the facts recap count and the
  // resume-window guard below (a catalogue-linked resume can hit this step before
  // SEED_INTAKE has re-derived intakePrefillBases from the resolved response).
  const prefillQuery = usePrefill(catalogueProductId);
  const register = useRegister();

  const vocabQueries = [usageContexts, humanOversightTypes, dataCategories, affectedParties, operatorRoles];
  // Custom systems never seed field_prefills (D-70) — intakePrefillBases stays
  // permanently null for them, so the resume-window wait only applies when a
  // catalogue product is actually driving prefill.
  const isPrefillPending = Boolean(catalogueProductId) && (prefillQuery.isLoading || intakePrefillBases === null);
  const isLoading = vocabQueries.some((q) => q.isLoading) || categoryMemberships.isLoading || isPrefillPending;
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

  // FE-36 (E-compact): the pre-commit disposition gate. derivedItems carries every
  // derived field (confirmed or not) so an already-confirmed one still shows its
  // indicator; Register is gated on the unconfirmed subset, computed via the same
  // shared predicate IntakeCaptureStep uses (V2) so the two can't diverge.
  const derivedFieldMeta: { field: IntakeFieldName; label: string; value: string | null; options: SelectOption[] }[] = [
    { field: "operatorRoleId", label: "Operator role", value: operatorRoleId, options: toOptions(operatorRoles.data) },
    { field: "lifecycleStage", label: "Lifecycle stage", value: lifecycleStage, options: LIFECYCLE_STAGE_OPTIONS },
  ];
  const derivedItems: DerivedDispositionItem[] = derivedFieldMeta
    .filter((f) => intakePrefillBases?.[f.field as keyof IntakePrefillBases] === "derived")
    .map((f) => ({
      field: f.field,
      label: f.label,
      value: f.value ?? "",
      options: f.options,
      confirmed: confirmedIntakeFields.includes(f.field),
    }));
  const unconfirmed = derivedUnconfirmed(intakePrefillBases, confirmedIntakeFields);
  const canRegister = unconfirmed.length === 0;
  const gateNote =
    unconfirmed.length > 0
      ? `Confirm ${unconfirmed
          .map((f) => derivedFieldMeta.find((m) => m.field === f)?.label.toLowerCase())
          .join(" and ")} to continue.`
      : null;

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!canRegister) return;
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
        // FE-32/INV-83: disposition signal (D-74).
        // Intake fields: camelCase → API snake_case.
        // Fact keys: "fact:<key>" for confirmed, "fact_amended:<key>" for amended (WI-6).
        confirmed_fields: [
          ...confirmedIntakeFields.map((f) => INTAKE_FIELD_API_KEY[f] ?? f),
          ...confirmedFactKeys.map((k) => `fact:${k}`),
          ...amendedFactKeys.map((k) => `fact_amended:${k}`),
        ],
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
      <form aria-label="use-case-create" onSubmit={handleSubmit} className="bg-paper shadow-[var(--elevation-raised)] space-y-4 rounded-lg p-4">
        <SectionGroup title="Use & oversight">
          <div className="space-y-4">
            <TextInput
              id="use-case-title"
              label="What are you using this for?"
              value={title}
              onChange={setTitle}
              required
              placeholder="e.g. Screening inbound support tickets"
            />

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
          </div>
        </SectionGroup>

        <SectionGroup title="Data & affected parties">
          <div className="space-y-4">
            <GroupedMultiSelect
              id="data-categories"
              label="Data categories"
              values={dataCategoryIds}
              options={(dataCategories.data ?? []).map((c) => ({
                value: c.id,
                label: c.label,
                group: c.is_special_category ? "duty" : "other",
              }))}
              onChange={setDataCategoryIds}
              dutyHeading="Special-category data"
              dutyCaption="GDPR Art. 9, heightened duty"
              otherHeading="Other personal data"
            />
            <GroupedMultiSelect
              id="affected-parties"
              label="Affected parties"
              values={affectedPartyIds}
              options={(affectedParties.data ?? []).map((p) => ({
                value: p.id,
                label: p.label,
                group: p.is_vulnerable_group ? "duty" : "other",
              }))}
              onChange={setAffectedPartyIds}
              dutyHeading="Vulnerable groups"
              dutyCaption="EU AI Act Art. 27, heightened duty"
              otherHeading="Other affected parties"
            />
          </div>
        </SectionGroup>

        <PreCommitDispositionGate
          derivedItems={derivedItems}
          onConfirm={onConfirmField}
          onChange={(field, value) => onFieldChange(field, value)}
          factCount={prefillQuery.data?.facts.length ?? 0}
          onReviewFacts={onReviewFacts}
        />

        {register.isError && (
          <div role="alert" className="text-sm text-danger">Could not register this system and use case. Check the form and try again.</div>
        )}

        <div className="flex items-center gap-3.5">
          <Button type="submit" disabled={register.isPending || !canRegister}>
            Register
          </Button>
          {gateNote && <span className="text-xs text-ink-muted">{gateNote}</span>}
        </div>
      </form>
    </PageScaffold>
  );
}
