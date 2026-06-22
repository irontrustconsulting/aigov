import { isYourCourt, resolveCourt } from "../court";
import type { GateResultRead } from "@irontrust/api-client";

function blocking(overrides: Partial<GateResultRead>): GateResultRead {
  return {
    state: "intake",
    verdict: "park",
    reason_code: "no_aiia",
    reason: "No assessment started for this use case",
    responsible_party: "user",
    ...overrides,
  };
}

describe("resolveCourt", () => {
  test("null blocking resolves to no court", () => {
    expect(resolveCourt(null)).toBeNull();
  });

  test("responsible_party 'user' maps to the system_owner role (the B1 regression case, not-pending)", () => {
    const court = resolveCourt(blocking({ responsible_party: "user" }));
    expect(court?.roleKey).toBe("system_owner");
  });

  test("a context-path PENDING_REVIEW use case resolves to reviewer, not owner (the B1 regression test)", () => {
    const court = resolveCourt(
      blocking({
        reason_code: "tier_not_ratified",
        reason: "Classification tier not yet ratified (eu_tier pending)",
        responsible_party: "reviewer",
      })
    );
    expect(court?.roleKey).toBe("reviewer");
  });

  test("responsible_party 'authoriser' maps 1:1", () => {
    expect(resolveCourt(blocking({ responsible_party: "authoriser" }))?.roleKey).toBe("authoriser");
  });

  test("responsible_party 'vendor' matches no governance role", () => {
    expect(resolveCourt(blocking({ responsible_party: "vendor" }))?.roleKey).toBeNull();
  });

  test("responsible_party 'system' matches no governance role", () => {
    expect(resolveCourt(blocking({ responsible_party: "system" }))?.roleKey).toBeNull();
  });
});

describe("isYourCourt", () => {
  test("null court is never your court", () => {
    expect(isYourCourt(null, new Set(["system_owner"]))).toBe(false);
  });

  test("a court with no role match (vendor/system) is never your court, for any caller", () => {
    const court = resolveCourt(blocking({ responsible_party: "vendor" }));
    expect(isYourCourt(court, new Set(["system_owner", "reviewer", "authoriser", "auditor", "contributor"]))).toBe(
      false
    );
  });

  test("auditor never matches a court — 3rd line, never a blocking party", () => {
    const court = resolveCourt(blocking({ responsible_party: "reviewer" }));
    expect(isYourCourt(court, new Set(["auditor"]))).toBe(false);
  });

  test("contributor is never emitted as a responsible_party, so contributor never matches either", () => {
    const court = resolveCourt(blocking({ responsible_party: "user" }));
    expect(isYourCourt(court, new Set(["contributor"]))).toBe(false);
  });

  test("system_owner matches the 'user' party", () => {
    const court = resolveCourt(blocking({ responsible_party: "user" }));
    expect(isYourCourt(court, new Set(["system_owner"]))).toBe(true);
  });

  test("reviewer matches the 'reviewer' party", () => {
    const court = resolveCourt(blocking({ responsible_party: "reviewer" }));
    expect(isYourCourt(court, new Set(["reviewer"]))).toBe(true);
  });

  test("authoriser matches the 'authoriser' party", () => {
    const court = resolveCourt(blocking({ responsible_party: "authoriser" }));
    expect(isYourCourt(court, new Set(["authoriser"]))).toBe(true);
  });

  test("a caller without the matching role does not get a false-positive highlight", () => {
    const court = resolveCourt(blocking({ responsible_party: "reviewer" }));
    expect(isYourCourt(court, new Set(["system_owner"]))).toBe(false);
  });
});
