import { NextRequest } from "next/server";

beforeAll(() => {
  process.env.COGNITO_REGION = "eu-west-2";
  process.env.COGNITO_USER_POOL_ID = "eu-west-2_test";
  process.env.COGNITO_APP_CLIENT_ID = "test-client-id";
  process.env.COGNITO_DOMAIN = "irontrustai-users-dev";
  process.env.APP_ORIGIN = "http://localhost:3000";
});

describe("POST /api/auth/logout", () => {
  test("same-origin request is accepted and clears the session cookie", async () => {
    const { POST } = await import("../logout/route");
    const request = new NextRequest("http://localhost:3000/api/auth/logout", {
      method: "POST",
      headers: { "sec-fetch-site": "same-origin" },
    });
    const response = await POST(request);
    expect(response.status).toBe(200);
  });

  test("cross-origin POST without same-origin Sec-Fetch-Site is rejected", async () => {
    const { POST } = await import("../logout/route");
    const request = new NextRequest("http://localhost:3000/api/auth/logout", {
      method: "POST",
      headers: { "sec-fetch-site": "cross-site", origin: "http://evil.example" },
    });
    const response = await POST(request);
    expect(response.status).toBe(403);
  });
});
