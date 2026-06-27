/**
 * WI-2 done-check: assert the runtime guard (FE-9, INV-3, INV-13) covers
 * the F1 mutation bodies — SystemCreate, UseCaseCreate, ComputeRequest —
 * for a forbidden field that arrives via an untyped path (`as any`/spread),
 * since `MutationBody<T>` only blocks it at compile time.
 */
import { assertNoForbiddenFields, ForbiddenFieldError } from "../../guards";
import type { ComputeRequest } from "../classification-context";
import type { SystemCreate } from "../system";
import type { UseCaseCreate } from "../use-case";

describe("F1 mutation bodies reject forbidden fields at the runtime boundary", () => {
  test("SystemCreate rejects a client-supplied tenant_id", () => {
    const body = {
      name: "Test System",
      is_custom: true,
      catalogue_product_id: null,
      catalogue_vendor_id: null,
      owner_user_id: null,
      operator_role_id: null,
      hosting_model_id: null,
      lifecycle_stage: null,
      purpose: null,
      tenant_id: "evil",
    } as SystemCreate & { tenant_id: string };
    expect(() => assertNoForbiddenFields(body)).toThrow(ForbiddenFieldError);
  });

  test("UseCaseCreate rejects a client-supplied tenant_id", () => {
    const body = {
      system_id: "sys-1",
      title: "Test use case",
      purpose: null,
      context_blob: {},
      tenant_id: "evil",
    } as UseCaseCreate & { tenant_id: string };
    expect(() => assertNoForbiddenFields(body)).toThrow(ForbiddenFieldError);
  });

  test("ComputeRequest rejects a client-supplied provenance nested in an answer", () => {
    const body: ComputeRequest = {
      answers: [{ question_code: "q1", option_code: "opt-a" }],
      tree_version: "v1",
      override_tier: null,
      justification: null,
    };
    const tampered = {
      ...body,
      answers: [{ ...body.answers[0], provenance: "ai_suggested" }],
    };
    expect(() => assertNoForbiddenFields(tampered)).toThrow(ForbiddenFieldError);
  });

  test("a clean ComputeRequest (answers without provenance) passes", () => {
    const body: ComputeRequest = {
      answers: [{ question_code: "q1", option_code: "opt-a" }],
      tree_version: "v1",
      override_tier: null,
      justification: null,
    };
    expect(() => assertNoForbiddenFields(body)).not.toThrow();
  });
});
