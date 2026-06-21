"use client";

import { useReducer } from "react";
import { useMe } from "@/lib/intake";
import { initialWizardState, wizardReducer } from "./wizard-state";
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

/**
 * UI-F1-INTAKE: the tenant intake/registration wizard. Role-aware (WI-10,
 * FE-8, UX-5) — only a system_owner drives the capture spine; the lifecycle
 * state itself is never mutated client-side (the wizard only reads it,
 * WI-9), and the wizard's `step` is a navigation cursor, not a lifecycle
 * state.
 */
export default function NewSystemPage() {
  const me = useMe();
  const [state, dispatch] = useReducer(wizardReducer, initialWizardState);

  if (me.isLoading) return <p>Loading…</p>;
  if (me.isError || !me.data) return <p role="alert">Could not load your role.</p>;

  const roleKeys = new Set(me.data.governance_roles.map((r) => r.key));
  const isSystemOwner = roleKeys.has("system_owner");
  const isAssurance = [...roleKeys].some((k) => ASSURANCE_ROLE_KEYS.has(k));

  if (!isSystemOwner) {
    return isAssurance ? <AssuranceReadOnly /> : <NeedsSystemOwner />;
  }

  switch (state.step) {
    case "drill-down":
      return (
        <DrillDownStep
          onComplete={(result) =>
            dispatch({
              type: "DRILL_DOWN_COMPLETE",
              isCustom: result.isCustom,
              catalogueProductId: result.catalogueProductId,
              catalogueProductName: result.catalogueProductName,
            })
          }
        />
      );

    case "intake":
      return (
        <IntakeCaptureStep
          isCustom={state.isCustom}
          catalogueProductId={state.catalogueProductId}
          onSubmit={(system) => dispatch({ type: "SYSTEM_CREATED", system })}
        />
      );

    case "prefill":
      return (
        <PrefillStep
          systemId={state.system!.id}
          onContinue={() => dispatch({ type: "PREFILL_DONE" })}
        />
      );

    case "use-case":
      return (
        <UseCaseCreateStep
          systemId={state.system!.id}
          onCreated={(useCaseId, classification) =>
            dispatch({ type: "USE_CASE_CREATED", useCaseId, classification })
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
