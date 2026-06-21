import { NextRequest } from "next/server";
import { SESSION_COOKIE_NAME } from "@/lib/auth/constants";
import { sessionStore } from "@/lib/auth/in-memory-session-store";

beforeAll(() => {
  process.env.COGNITO_OPERATOR_REGION = "eu-west-2";
  process.env.COGNITO_OPERATOR_USER_POOL_ID = "eu-west-2_test";
  process.env.COGNITO_OPERATOR_APP_CLIENT_ID = "test-client-id";
  process.env.COGNITO_OPERATOR_DOMAIN = "irontrustai-operators-dev";
  process.env.APP_ORIGIN = "http://localhost:3001";
});

afterEach(() => {
  jest.restoreAllMocks();
});

describe("POST /api/auth/refresh", () => {
  test("rotates the stored token server-side without exposing it to the response body", async () => {
    const sessionId = await sessionStore.create({
      idToken: "old-id-token",
      refreshToken: "refresh-token-value",
      expiresAt: Date.now(),
      createdAt: Date.now(),
      lastSeenAt: Date.now(),
      userSub: "user-sub-123",
    });

    jest.spyOn(global, "fetch").mockResolvedValue({
      ok: true,
      json: async () => ({
        id_token: "new-id-token",
        access_token: "new-access-token",
        expires_in: 3600,
        token_type: "Bearer",
      }),
      text: async () => "",
    } as Response);

    const { POST } = await import("../refresh/route");
    const request = new NextRequest("http://localhost:3001/api/auth/refresh", {
      method: "POST",
      headers: {
        "sec-fetch-site": "same-origin",
        cookie: `${SESSION_COOKIE_NAME}=${sessionId}`,
      },
    });

    const response = await POST(request);
    expect(response.status).toBe(200);
    const body = await response.json();
    expect(body).toEqual({ ok: true });

    const updated = await sessionStore.get(sessionId);
    expect(updated?.idToken).toBe("new-id-token");
  });

  test("401s with no session cookie", async () => {
    const { POST } = await import("../refresh/route");
    const request = new NextRequest("http://localhost:3001/api/auth/refresh", {
      method: "POST",
      headers: { "sec-fetch-site": "same-origin" },
    });
    const response = await POST(request);
    expect(response.status).toBe(401);
  });
});
