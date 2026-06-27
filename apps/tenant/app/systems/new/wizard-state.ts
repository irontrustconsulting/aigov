import type { ClassificationRead, SystemDetail } from "@irontrust/api-client";

/**
 * UI-F1-INTAKE: the wizard's cross-step state. The wizard reads lifecycle
 * state from the server (WI-9) and never derives it itself — `step` here is
 * purely a UI navigation cursor, not a lifecycle state (the sprint's
 * "no client mutation of state" rule applies to use_case.state, not to
 * which screen the wizard is showing).
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
  isCustom: boolean;
  catalogueProductId: string | null;
  catalogueProductName: string | null;
  system: SystemDetail | null;
  useCaseId: string | null;
  classification: ClassificationRead | null;
  /** Use-distinguishing context captured in intake step, written on use-case create (DM-S1/DF-D1-2). */
  usageContextId: string | null;
  humanOversightTypeId: string | null;
  dataCategoryIds: string[];
  affectedPartyIds: string[];
}

export const initialWizardState: WizardState = {
  step: "drill-down",
  isCustom: false,
  catalogueProductId: null,
  catalogueProductName: null,
  system: null,
  useCaseId: null,
  classification: null,
  usageContextId: null,
  humanOversightTypeId: null,
  dataCategoryIds: [],
  affectedPartyIds: [],
};

export type WizardAction =
  | { type: "DRILL_DOWN_COMPLETE"; isCustom: boolean; catalogueProductId: string | null; catalogueProductName: string | null }
  | { type: "SYSTEM_CREATED"; system: SystemDetail; usageContextId: string | null; humanOversightTypeId: string | null; dataCategoryIds: string[]; affectedPartyIds: string[] }
  | { type: "PREFILL_DONE" }
  | { type: "USE_CASE_CREATED"; useCaseId: string; classification: ClassificationRead }
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
    case "SYSTEM_CREATED":
      return {
        ...state,
        step: "prefill",
        system: action.system,
        usageContextId: action.usageContextId,
        humanOversightTypeId: action.humanOversightTypeId,
        dataCategoryIds: action.dataCategoryIds,
        affectedPartyIds: action.affectedPartyIds,
      };
    case "PREFILL_DONE":
      return { ...state, step: "use-case" };
    case "USE_CASE_CREATED": {
      if (action.classification.requires_context) {
        return {
          ...state,
          step: "context-gate",
          useCaseId: action.useCaseId,
          classification: action.classification,
        };
      }
      if (action.classification.tier === "prohibited") {
        return {
          ...state,
          step: "terminal-prohibited",
          useCaseId: action.useCaseId,
          classification: action.classification,
        };
      }
      return {
        ...state,
        step: "use-case-resolved",
        useCaseId: action.useCaseId,
        classification: action.classification,
      };
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
