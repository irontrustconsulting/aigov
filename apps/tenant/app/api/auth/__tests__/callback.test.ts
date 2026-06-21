import { NextRequest } from "next/server";
import { PKCE_COOKIE_NAME, SESSION_COOKIE_NAME } from "@/lib/auth/constants";

function fakeIdToken(sub: string): string {
  const header = Buffer.from(JSON.stringify({ alg: "none" })).toString("base64url");
  const payload = Buffer.from(JSON.stringify({ sub })).toString("base64url");
  return `${header}.${payload}.sig`;
}

beforeAll(() => {
  process.env.COGNITO_REGION = "eu-west-2";
  process.env.COGNITO_USER_POOL_ID = "eu-west-2_test";
  process.env.COGNITO_APP_CLIENT_ID = "test-client-id";
  process.env.COGNITO_DOMAIN = "irontrustai-users-dev";
  process.env.APP_ORIGIN = "http://localhost:3000";
});

afterEach(() => {
  jest.restoreAllMocks();
});

function requestWithPkceCookie(query: string, pkceValue: string | null): NextRequest {
  const headers: Record<string, string> = {};
  if (pkceValue !== null) {
    headers.cookie = `${PKCE_COOKIE_NAME}=${encodeURIComponent(pkceValue)}`;
  }
  return new NextRequest(`http://localhost:3000/api/auth/callback${query}`, { headers });
}

describe("GET /api/auth/callback", () => {
  test("login -> callback sets an opaque session cookie (not a token)", async () => {
    const tokenResponse = {
      id_token: fakeIdToken("user-sub-123"),
      access_token: "access-token-value",
      refresh_token: "refresh-token-value",
      expires_in: 3600,
      token_type: "Bearer",
    };
    jest.spyOn(global, "fetch").mockResolvedValue({
      ok: true,
      json: async () => tokenResponse,
      text: async () => "",
    } as Response);

    const { GET } = await import("../callback/route");
    const pkceValue = JSON.stringify({ verifier: "verifier-abc", state: "state-xyz" });
    const request = requestWithPkceCookie("?code=auth-code-1&state=state-xyz", pkceValue);

    const response = await GET(request);

    expect(response.status).toBe(307);
    const sessionCookie = response.cookies.get(SESSION_COOKIE_NAME);
    expect(sessionCookie).toBeDefined();

    // The cookie value must be opaque — not JWT-shaped (no two dots), and not
    // decodable as the kind of JSON a token payload would produce.
    const value = sessionCookie!.value;
    expect(value.split(".").length).not.toBe(3);
    expect(() => Buffer.from(value, "base64url").toString("utf-8")).not.toThrow();
    expect(value).not.toContain(tokenResponse.id_token);
    expect(value).not.toContain(tokenResponse.access_token);

    // The PKCE handshake cookie is cleared regardless of outcome.
    const pkceCookie = response.cookies.get(PKCE_COOKIE_NAME);
    expect(pkceCookie?.value).toBe("");
  });

  test("rejects a state mismatch", async () => {
    const { GET } = await import("../callback/route");
    const pkceValue = JSON.stringify({ verifier: "verifier-abc", state: "state-xyz" });
    const request = requestWithPkceCookie("?code=auth-code-1&state=WRONG", pkceValue);

    const response = await GET(request);
    expect(response.status).toBe(400);
  });

  test("rejects a missing PKCE handshake cookie", async () => {
    const { GET } = await import("../callback/route");
    const request = requestWithPkceCookie("?code=auth-code-1&state=state-xyz", null);

    const response = await GET(request);
    expect(response.status).toBe(400);
  });
});
