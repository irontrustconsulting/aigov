import { NextRequest } from "next/server";
import { isSameOriginRequest } from "../csrf";

function makeRequest(headers: Record<string, string>): NextRequest {
  return new NextRequest("http://localhost:3000/api/auth/logout", {
    method: "POST",
    headers,
  });
}

describe("isSameOriginRequest", () => {
  test("accepts Sec-Fetch-Site: same-origin", () => {
    expect(isSameOriginRequest(makeRequest({ "sec-fetch-site": "same-origin" }))).toBe(true);
  });

  test("rejects Sec-Fetch-Site: cross-site", () => {
    expect(isSameOriginRequest(makeRequest({ "sec-fetch-site": "cross-site" }))).toBe(false);
  });

  test("falls back to Origin header matching the app origin when Sec-Fetch-Site is absent", () => {
    expect(isSameOriginRequest(makeRequest({ origin: "http://localhost:3000" }))).toBe(true);
  });

  test("rejects a mismatched Origin when Sec-Fetch-Site is absent", () => {
    expect(isSameOriginRequest(makeRequest({ origin: "http://evil.example" }))).toBe(false);
  });

  test("rejects when neither Sec-Fetch-Site nor Origin/Referer is present", () => {
    expect(isSameOriginRequest(makeRequest({}))).toBe(false);
  });
});
