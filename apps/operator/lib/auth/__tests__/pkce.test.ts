import { generateCodeVerifier, generateCodeChallenge, generateState } from "../pkce";

describe("pkce", () => {
  test("verifier is URL-safe and within RFC 7636 length bounds", () => {
    const v = generateCodeVerifier();
    expect(v.length).toBeGreaterThanOrEqual(43);
    expect(v.length).toBeLessThanOrEqual(128);
    expect(v).toMatch(/^[A-Za-z0-9_-]+$/);
  });

  test("challenge is deterministic for a given verifier and differs from it", () => {
    const v = generateCodeVerifier();
    const c1 = generateCodeChallenge(v);
    const c2 = generateCodeChallenge(v);
    expect(c1).toBe(c2);
    expect(c1).not.toBe(v);
  });

  test("state is URL-safe and random across calls", () => {
    const s1 = generateState();
    const s2 = generateState();
    expect(s1).toMatch(/^[A-Za-z0-9_-]+$/);
    expect(s1).not.toBe(s2);
  });
});
