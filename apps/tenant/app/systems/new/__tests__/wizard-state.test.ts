import { initialWizardState, wizardReducer, type WizardAction } from "../wizard-state";
import type { ClassificationRead, RegistrationRead } from "@irontrust/api-client";

function classification(overrides: Partial<ClassificationRead>): ClassificationRead {
  return {
    id: "c1",
    use_case_id: "uc-1",
    tier: "minimal_risk",
    rationale: "r",
    version: 1,
    is_current: true,
    overridden: false,
    proposed_tier: null,
    basis_subcategory_code: null,
    basis_legal_ref: null,
    requires_context: false,
    ...overrides,
  };
}

function registrationResult(classificationOverrides: Partial<ClassificationRead>): RegistrationRead {
  return {
    system: {
      id: "sys-1",
      name: "Test",
      is_custom: false,
      catalogue_product: null,
      catalogue_vendor: null,
      owner_user_id: null,
      operator_role: null,
      hosting_model: null,
      lifecycle_stage: null,
      purpose: null,
      use_case_count: 0,
      use_case_lifecycle_states: [],
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-01T00:00:00Z",
    },
    use_case: {
      id: "uc-1",
      tenant_id: "t1",
      system_id: "sys-1",
      title: "x",
      purpose: null,
      state: "intake",
      eu_tier: "unclassified",
      usage_context: null,
      human_oversight_type: null,
      data_categories: [],
      affected_parties: [],
    },
    classification: classification(classificationOverrides),
  };
}

function registrationAction(classificationOverrides: Partial<ClassificationRead>): WizardAction {
  return {
    type: "REGISTERED",
    result: registrationResult(classificationOverrides),
    usageContextId: null,
    humanOversightTypeId: null,
    dataCategoryIds: [],
    affectedPartyIds: [],
  };
}

describe("wizardReducer REGISTERED branch precedence (sprint § branch order)", () => {
  test("requires_context true takes precedence and routes to context-gate, even if tier looks resolved", () => {
    const action = registrationAction({ requires_context: true, tier: "high_risk" });
    const next = wizardReducer(initialWizardState, action);
    expect(next.step).toBe("context-gate");
  });

  test("tier=prohibited (requires_context false) routes to the terminal hard-stop", () => {
    const action = registrationAction({ requires_context: false, tier: "prohibited" });
    const next = wizardReducer(initialWizardState, action);
    expect(next.step).toBe("terminal-prohibited");
  });

  test("a concrete, non-prohibited tier routes to the resolved-tier step (override ladder), not straight to whose-court", () => {
    const action = registrationAction({ requires_context: false, tier: "high_risk" });
    const next = wizardReducer(initialWizardState, action);
    expect(next.step).toBe("use-case-resolved");
    expect(next.useCaseId).toBe("uc-1");
  });

  test("PROCEED_TO_WHOSE_COURT advances from the resolved-tier step to whose-court", () => {
    const resolved = wizardReducer(initialWizardState, registrationAction({ tier: "high_risk" }));
    const next = wizardReducer(resolved, { type: "PROCEED_TO_WHOSE_COURT" });
    expect(next.step).toBe("whose-court");
  });
});

describe("wizardReducer context-gate outcomes", () => {
  test("CONTEXT_PROHIBITED_HALT routes to the terminal hard-stop", () => {
    const next = wizardReducer(initialWizardState, { type: "CONTEXT_PROHIBITED_HALT" });
    expect(next.step).toBe("terminal-prohibited");
  });

  test("CONTEXT_RESOLVED routes to whose-court", () => {
    const next = wizardReducer(initialWizardState, { type: "CONTEXT_RESOLVED", useCaseId: "uc-1" });
    expect(next.step).toBe("whose-court");
  });
});
