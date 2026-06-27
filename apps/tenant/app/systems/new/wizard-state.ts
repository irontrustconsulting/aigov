import type { ClassificationRead, RegistrationRead, SystemDetail, SystemLifecycleStage } from "@irontrust/api-client";

/**
 * UI-F1-INTAKE: the wizard's cross-step state. The wizard reads lifecycle
 * state from the server (WI-9) and never derives it itself — `step` here is
 * purely a UI navigation cursor, not a lifecycle state (the sprint's
 * "no client mutation of state" rule applies to use_case.state, not to
 * which screen the wizard is showing).
 *
 * DM-S2 (DF-D2-3): system-stable facts are held in state through drill-down
 * → intake → prefill → use-case; POST /v1/registrations fires once at the
 * use-case step. No early POST /systems.
 */
export type WizardStep =
  | "drill-down"
  | "intake"
  | "prefill"
  | "use-case"
  | "use-case-resolved"
  | "context-gate"
  | "terminal-prohibited"
  | "whose-court";

export interface WizardState {
  step: WizardStep;
  // Drill-down selection
  isCustom: boolean;
  catalogueProductId: string | null;
  catalogueProductName: string | null;
  // System-stable facts captured at intake step (DF-D2-1)
  name: string;
  operatorRoleId: string | null;
  hostingModelId: string | null;
  lifecycleStage: SystemLifecycleStage | null;
  purpose: string | null;
  // Use-distinguishing context captured at use-case step (closes DF-D1-2)
  usageContextId: string | null;
  humanOversightTypeId: string | null;
  dataCategoryIds: string[];
  affectedPartyIds: string[];
  // Post-registration (populated by REGISTERED)
  system: SystemDetail | null;
  useCaseId: string | null;
  classification: ClassificationRead | null;
}

export const initialWizardState: WizardState = {
  step: "drill-down",
  isCustom: false,
  catalogueProductId: null,
  catalogueProductName: null,
  name: "",
  operatorRoleId: null,
  hostingModelId: null,
  lifecycleStage: null,
  purpose: null,
  usageContextId: null,
  humanOversightTypeId: null,
  dataCategoryIds: [],
  affectedPartyIds: [],
  system: null,
  useCaseId: null,
  classification: null,
};

export type WizardAction =
  | {
      type: "DRILL_DOWN_COMPLETE";
      isCustom: boolean;
      catalogueProductId: string | null;
      catalogueProductName: string | null;
    }
  | {
      type: "INTAKE_DONE";
      name: string;
      operatorRoleId: string | null;
      hostingModelId: string | null;
      lifecycleStage: SystemLifecycleStage | null;
      purpose: string | null;
    }
  | { type: "PREFILL_DONE" }
  | {
      type: "REGISTERED";
      result: RegistrationRead;
      usageContextId: string | null;
      humanOversightTypeId: string | null;
      dataCategoryIds: string[];
      affectedPartyIds: string[];
    }
  | { type: "CONTEXT_RESOLVED"; useCaseId: string }
  | { type: "CONTEXT_PROHIBITED_HALT" }
  | { type: "OVERRIDE_APPLIED"; classification: ClassificationRead }
  | { type: "PROCEED_TO_WHOSE_COURT" };

export function wizardReducer(state: WizardState, action: WizardAction): WizardState {
  switch (action.type) {
    case "DRILL_DOWN_COMPLETE":
      return {
        ...state,
        step: "intake",
        isCustom: action.isCustom,
        catalogueProductId: action.catalogueProductId,
        catalogueProductName: action.catalogueProductName,
      };

    case "INTAKE_DONE":
      return {
        ...state,
        step: "prefill",
        name: action.name,
        operatorRoleId: action.operatorRoleId,
        hostingModelId: action.hostingModelId,
        lifecycleStage: action.lifecycleStage,
        purpose: action.purpose,
      };

    case "PREFILL_DONE":
      return { ...state, step: "use-case" };

    case "REGISTERED": {
      const { system, use_case, classification } = action.result;
      const base = {
        ...state,
        system,
        useCaseId: use_case.id,
        classification,
        usageContextId: action.usageContextId,
        humanOversightTypeId: action.humanOversightTypeId,
        dataCategoryIds: action.dataCategoryIds,
        affectedPartyIds: action.affectedPartyIds,
      };
      if (classification.requires_context) return { ...base, step: "context-gate" };
      if (classification.tier === "prohibited") return { ...base, step: "terminal-prohibited" };
      return { ...base, step: "use-case-resolved" };
    }

    case "OVERRIDE_APPLIED":
      return { ...state, classification: action.classification };

    case "PROCEED_TO_WHOSE_COURT":
      return { ...state, step: "whose-court" };

    case "CONTEXT_RESOLVED":
      return { ...state, step: "whose-court" };

    case "CONTEXT_PROHIBITED_HALT":
      return { ...state, step: "terminal-prohibited" };

    default:
      return state;
  }
}
