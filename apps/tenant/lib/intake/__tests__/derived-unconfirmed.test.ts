import { derivedUnconfirmed } from "../derived-unconfirmed";

describe("derivedUnconfirmed (V2, FIX-RESUME-REGATE)", () => {
  test("returns fields whose basis is derived and not yet confirmed", () => {
    const result = derivedUnconfirmed(
      { operatorRoleId: "derived", lifecycleStage: "derived" },
      []
    );
    expect(result).toEqual(["operatorRoleId", "lifecycleStage"]);
  });

  test("excludes a derived field once confirmed", () => {
    const result = derivedUnconfirmed(
      { operatorRoleId: "derived", lifecycleStage: "derived" },
      ["operatorRoleId"]
    );
    expect(result).toEqual(["lifecycleStage"]);
  });

  test("excludes fields whose basis is catalogue or user-set", () => {
    const result = derivedUnconfirmed(
      { operatorRoleId: "catalogue", lifecycleStage: "user-set" },
      []
    );
    expect(result).toEqual([]);
  });

  test("returns empty when prefillBases is null", () => {
    expect(derivedUnconfirmed(null, [])).toEqual([]);
  });

  test("returns empty when both derived fields are confirmed", () => {
    const result = derivedUnconfirmed(
      { operatorRoleId: "derived", lifecycleStage: "derived" },
      ["operatorRoleId", "lifecycleStage"]
    );
    expect(result).toEqual([]);
  });

  test("only ever considers operatorRoleId and lifecycleStage, never hostingModelId/purpose", () => {
    const result = derivedUnconfirmed(
      { hostingModelId: "derived", purpose: "derived" } as never,
      []
    );
    expect(result).toEqual([]);
  });
});
