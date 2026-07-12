import { initialWizardState, wizardReducer, clampStep, type WizardAction } from "../wizard-state";
import type { ClassificationRead, DraftRegistrationRead, RegistrationRead } from "@irontrust/api-client";

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
    status: "approved",
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

  test("tier=prohibited (requires_context false, status=approved) routes to the terminal hard-stop", () => {
    const action = registrationAction({ requires_context: false, tier: "prohibited", status: "approved" });
    const next = wizardReducer(initialWizardState, action);
    expect(next.step).toBe("terminal-prohibited");
  });

  test("DOWN_SELECTION (status=pending_review, non-prohibited) routes to whose-court for reviewer sign-off (D-73)", () => {
    const action = registrationAction({ requires_context: false, tier: "high_risk", status: "pending_review" });
    const next = wizardReducer(initialWizardState, action);
    expect(next.step).toBe("whose-court");
  });

  test("AUTHORITATIVE (status=approved, non-prohibited) routes to the resolved-tier step", () => {
    const action = registrationAction({ requires_context: false, tier: "high_risk", status: "approved" });
    const next = wizardReducer(initialWizardState, action);
    expect(next.step).toBe("use-case-resolved");
    expect(next.useCaseId).toBe("uc-1");
  });

  test("PROCEED_TO_WHOSE_COURT advances from the resolved-tier step to whose-court", () => {
    const resolved = wizardReducer(initialWizardState, registrationAction({ tier: "high_risk", status: "approved" }));
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

describe("resumeResolved (UI-DRAFT-RESUME-GATE, INV-85)", () => {
  test("initialWizardState.resumeResolved is false", () => {
    expect(initialWizardState.resumeResolved).toBe(false);
  });

  function draft(blob: Record<string, unknown>): DraftRegistrationRead {
    return {
      id: "draft-1",
      tenant_id: "t1",
      owner_user_id: "u1",
      draft_blob: blob,
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-01T00:00:00Z",
    };
  }

  test("RESUME_FROM_DRAFT sets resumeResolved true and preserves draftId/step restore", () => {
    const d = draft({ step: "intake", name: "Test" });
    const next = wizardReducer(initialWizardState, { type: "RESUME_FROM_DRAFT", draft: d });
    expect(next.resumeResolved).toBe(true);
    expect(next.draftId).toBe(d.id);
    expect(next.step).toBe(clampStep("intake"));
  });

  test("RESUME_FROM_DRAFT resolves intendedUseCategoryId to null (DF-UC-5, DF-D3-1: use-case fields are never persisted to draft_blob)", () => {
    const d = draft({ step: "intake", name: "Test" });
    const next = wizardReducer(initialWizardState, { type: "RESUME_FROM_DRAFT", draft: d });
    expect(next.intendedUseCategoryId).toBeNull();
  });

  test("DRAFT_CREATED sets resumeResolved true", () => {
    const next = wizardReducer(initialWizardState, { type: "DRAFT_CREATED", draftId: "draft-1" });
    expect(next.resumeResolved).toBe(true);
    expect(next.draftId).toBe("draft-1");
  });

  test("DRAFT_DISCARDED resets to a fresh wizard with resumeResolved true", () => {
    const dirty = wizardReducer(initialWizardState, { type: "DRAFT_CREATED", draftId: "draft-1" });
    const next = wizardReducer(dirty, { type: "DRAFT_DISCARDED" });
    expect(next).toEqual({ ...initialWizardState, resumeResolved: true });
    expect(next.step).toBe("drill-down");
    expect(next.draftId).toBeNull();
  });
});
