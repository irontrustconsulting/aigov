"use client";

import { useCallback, useEffect, useReducer } from "react";
import { ErrorState, ResumePrompt, Skeleton } from "@irontrust/ui";
import {
  useActiveDraft,
  useDiscardDraft,
  useGetOrCreateDraft,
  useMe,
  usePatchDraft,
  usePrefill,
} from "@/lib/intake";
import {
  PRE_BOUNDARY_STEPS,
  clampStep,
  initialWizardState,
  wizardReducer,
  type WizardState,
  type WizardStep,
} from "./wizard-state";
import { DrillDownStep } from "./_steps/drill-down-step";
import { IntakeCaptureStep } from "./_steps/intake-capture-step";
import { PrefillStep } from "./_steps/prefill-step";
import { UseCaseCreateStep } from "./_steps/use-case-create-step";
import { ResolvedTierStep } from "./_steps/resolved-tier-step";
import { ContextGateStep } from "./_steps/context-gate-step";
import { TerminalProhibited } from "./_steps/terminal-prohibited";
import { WhoseCourtStep } from "./_steps/whose-court-step";
import { NeedsSystemOwner } from "./_steps/needs-system-owner";
import { AssuranceReadOnly } from "./_steps/assurance-readonly";

const ASSURANCE_ROLE_KEYS = new Set(["reviewer", "authoriser", "auditor"]);

/** Extract only the pre-boundary fields that belong in draft_blob (DF-D3-1/DF-D3-2). */
function toDraftBlob(state: WizardState, nextStep: WizardStep): Record<string, unknown> {
  return {
    isCustom: state.isCustom,
    catalogueProductId: state.catalogueProductId,
    catalogueProductName: state.catalogueProductName,
    name: state.name,
    operatorRoleId: state.operatorRoleId,
    hostingModelId: state.hostingModelId,
    lifecycleStage: state.lifecycleStage,
    purpose: state.purpose,
    step: clampStep(nextStep),
  };
}

/**
 * UI-F1-INTAKE: the tenant intake/registration wizard. Role-aware (WI-10,
 * FE-8, UX-5) — only a system_owner drives the capture spine; the lifecycle
 * state itself is never mutated client-side (the wizard only reads it,
 * WI-9), and the wizard's `step` is a navigation cursor, not a lifecycle
 * state.
 *
 * DM-S2: registration is atomic — POST /v1/registrations fires once at the
 * use-case step (REGISTERED action). No early POST /systems.
 *
 * DM-S3 (D-66): persist-on-transition writes draft_blob on each pre-boundary
 * advance. On re-entry, useActiveDraft checks for an existing draft and
 * offers ResumePrompt (FE-28) before the wizard renders.
 */
export default function NewSystemPage() {
  const me = useMe();
  const [state, dispatch] = useReducer(wizardReducer, initialWizardState);

  const activeDraft = useActiveDraft();
  const getOrCreate = useGetOrCreateDraft();
  const patchDraft = usePatchDraft(state.draftId ?? "");
  const discard = useDiscardDraft();

  // DM-S4a: seed intake fields from catalogue/derived prefill (FE-30).
  // Disabled for custom systems (catalogueProductId null → hook is no-op).
  const prefillQuery = usePrefill(state.catalogueProductId);
  useEffect(() => {
    if (!prefillQuery.data) return;
    dispatch({
      type: "SEED_INTAKE",
      catalogueProductName: state.catalogueProductName,
      fieldPrefills: prefillQuery.data.field_prefills,
    });
  // Re-seed only when the prefill data or the product changes (not on every render).
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [prefillQuery.data]);

  /**
   * Called after every pre-boundary dispatch. On the first advance, creates
   * the draft (get-or-create); on subsequent advances, PATCHes draft_blob.
   * No PATCH fires on or after REGISTERED (DF-D3-2, DF-D3-3).
   */
  const persistTransition = useCallback(
    (currentState: WizardState, nextStep: WizardStep) => {
      if (!(PRE_BOUNDARY_STEPS as string[]).includes(nextStep)) return;
      const blob = toDraftBlob(currentState, nextStep);
      if (!currentState.draftId) {
        getOrCreate.mutate(undefined, {
          onSuccess: (draft) => {
            dispatch({ type: "DRAFT_CREATED", draftId: draft.id });
            // PATCH immediately with the current blob; patchDraft uses the
            // draftId from state which may not be updated yet, so call directly.
            patchDraft.mutate({ draft_blob: blob });
          },
        });
      } else {
        patchDraft.mutate({ draft_blob: blob });
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [state.draftId]
  );

  if (me.isLoading || activeDraft.isLoading) return <Skeleton />;
  if (me.isError || !me.data) return <ErrorState message="Could not load your role." onRetry={() => me.refetch()} />;

  const roleKeys = new Set(me.data.governance_roles.map((r) => r.key));
  const isSystemOwner = roleKeys.has("system_owner");
  const isAssurance = [...roleKeys].some((k) => ASSURANCE_ROLE_KEYS.has(k));

  if (!isSystemOwner) {
    return isAssurance ? <AssuranceReadOnly /> : <NeedsSystemOwner />;
  }

  // Front-door resume (FE-28, DM-S3): show ResumePrompt when an active draft
  // exists and the wizard has not yet advanced (draftId null, step drill-down).
  if (activeDraft.data && state.draftId === null && state.step === "drill-down") {
    const draft = activeDraft.data;
    const savedStep = (draft.draft_blob.step as string | undefined) ?? "drill-down";
    const productName = (draft.draft_blob.catalogueProductName as string | null | undefined) ?? null;
    return (
      <ResumePrompt
        productName={productName}
        savedStep={savedStep}
        lastEditedAt={draft.updated_at}
        onResume={() => dispatch({ type: "RESUME_FROM_DRAFT", draft })}
        onStartOver={() => discard.mutate(draft.id)}
      />
    );
  }

  switch (state.step) {
    case "drill-down":
      return (
        <DrillDownStep
          onComplete={(result) => {
            const nextState = {
              ...state,
              isCustom: result.isCustom,
              catalogueProductId: result.catalogueProductId,
              catalogueProductName: result.catalogueProductName,
            };
            dispatch({
              type: "DRILL_DOWN_COMPLETE",
              isCustom: result.isCustom,
              catalogueProductId: result.catalogueProductId,
              catalogueProductName: result.catalogueProductName,
            });
            persistTransition(nextState, "intake");
          }}
        />
      );

    case "intake":
      return (
        <IntakeCaptureStep
          isCustom={state.isCustom}
          name={state.name}
          operatorRoleId={state.operatorRoleId}
          hostingModelId={state.hostingModelId}
          lifecycleStage={state.lifecycleStage}
          purpose={state.purpose}
          prefillBases={state.intakePrefillBases}
          onFieldChange={(field, value) => dispatch({ type: "SET_INTAKE_FIELD", field, value })}
          onSubmit={() => {
            dispatch({ type: "INTAKE_DONE" });
            persistTransition(state, "prefill");
          }}
        />
      );

    case "prefill":
      return (
        <PrefillStep
          catalogueProductId={state.catalogueProductId}
          onContinue={() => {
            dispatch({ type: "PREFILL_DONE" });
            persistTransition(state, "use-case");
          }}
        />
      );

    case "use-case":
      return (
        <UseCaseCreateStep
          name={state.name}
          isCustom={state.isCustom}
          catalogueProductId={state.catalogueProductId}
          operatorRoleId={state.operatorRoleId}
          hostingModelId={state.hostingModelId}
          lifecycleStage={state.lifecycleStage}
          purpose={state.purpose}
          draftId={state.draftId}
          onCreated={(result, context) =>
            dispatch({
              type: "REGISTERED",
              result,
              usageContextId: context.usageContextId,
              humanOversightTypeId: context.humanOversightTypeId,
              dataCategoryIds: context.dataCategoryIds,
              affectedPartyIds: context.affectedPartyIds,
            })
          }
        />
      );

    case "use-case-resolved":
      return (
        <ResolvedTierStep
          useCaseId={state.useCaseId!}
          classification={state.classification!}
          onOverrideApplied={(classification) => dispatch({ type: "OVERRIDE_APPLIED", classification })}
          onContinue={() => dispatch({ type: "PROCEED_TO_WHOSE_COURT" })}
        />
      );

    case "context-gate":
      return (
        <ContextGateStep
          useCaseId={state.useCaseId!}
          onResolved={() => dispatch({ type: "CONTEXT_RESOLVED", useCaseId: state.useCaseId! })}
          onProhibitedHalt={() => dispatch({ type: "CONTEXT_PROHIBITED_HALT" })}
        />
      );

    case "terminal-prohibited":
      return <TerminalProhibited />;

    case "whose-court":
      return <WhoseCourtStep useCaseId={state.useCaseId!} />;

    default:
      return null;
  }
}
