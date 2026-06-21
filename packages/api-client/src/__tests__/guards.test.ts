import { assertNoForbiddenFields, ForbiddenFieldError } from "../guards";

describe("assertNoForbiddenFields", () => {
  test("passes for a clean body", () => {
    expect(() => assertNoForbiddenFields({ name: "x", count: 3 })).not.toThrow();
  });

  test("throws for a top-level tenant_id", () => {
    expect(() => assertNoForbiddenFields({ tenant_id: "evil" })).toThrow(ForbiddenFieldError);
  });

  test("throws for a nested provenance", () => {
    expect(() => assertNoForbiddenFields({ item: { provenance: "AI_SUGGESTED" } })).toThrow(
      ForbiddenFieldError
    );
  });

  test("throws for a forbidden key inside an array", () => {
    expect(() =>
      assertNoForbiddenFields({ items: [{ name: "ok" }, { tenant_id: "evil" }] })
    ).toThrow(ForbiddenFieldError);
  });
});
