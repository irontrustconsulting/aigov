import { initialWizardState, wizardReducer, type WizardAction } from "../wizard-state";
import type { ClassificationRead } from "@irontrust/api-client";

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

describe("wizardReducer USE_CASE_CREATED branch precedence (sprint § branch order)", () => {
  test("requires_context true takes precedence and routes to context-gate, even if tier looks resolved", () => {
    const action: WizardAction = {
      type: "USE_CASE_CREATED",
      useCaseId: "uc-1",
      classification: classification({ requires_context: true, tier: "high_risk" }),
    };
    const next = wizardReducer(initialWizardState, action);
    expect(next.step).toBe("context-gate");
  });

  test("tier=prohibited (requires_context false) routes to the terminal hard-stop", () => {
    const action: WizardAction = {
      type: "USE_CASE_CREATED",
      useCaseId: "uc-1",
      classification: classification({ requires_context: false, tier: "prohibited" }),
    };
    const next = wizardReducer(initialWizardState, action);
    expect(next.step).toBe("terminal-prohibited");
  });

  test("a concrete, non-prohibited tier routes to the resolved-tier step (override ladder), not straight to whose-court", () => {
    const action: WizardAction = {
      type: "USE_CASE_CREATED",
      useCaseId: "uc-1",
      classification: classification({ requires_context: false, tier: "high_risk" }),
    };
    const next = wizardReducer(initialWizardState, action);
    expect(next.step).toBe("use-case-resolved");
    expect(next.useCaseId).toBe("uc-1");
  });

  test("PROCEED_TO_WHOSE_COURT advances from the resolved-tier step to whose-court", () => {
    const resolved = wizardReducer(initialWizardState, {
      type: "USE_CASE_CREATED",
      useCaseId: "uc-1",
      classification: classification({ tier: "high_risk" }),
    });
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
