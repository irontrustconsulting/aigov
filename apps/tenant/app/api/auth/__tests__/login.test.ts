import { PKCE_COOKIE_NAME } from "@/lib/auth/constants";

beforeAll(() => {
  process.env.COGNITO_REGION = "eu-west-2";
  process.env.COGNITO_USER_POOL_ID = "eu-west-2_test";
  process.env.COGNITO_APP_CLIENT_ID = "test-client-id";
  process.env.COGNITO_DOMAIN = "irontrustai-users-dev";
  process.env.APP_ORIGIN = "http://localhost:3000";
});

describe("GET /api/auth/login", () => {
  test("redirects to the Cognito hosted-UI authorize endpoint and sets the PKCE handshake cookie", async () => {
    const { GET } = await import("../login/route");
    const response = await GET();

    expect(response.status).toBe(307);
    const location = response.headers.get("location")!;
    expect(location).toContain("irontrustai-users-dev.auth.eu-west-2.amazoncognito.com/oauth2/authorize");
    expect(location).toContain("response_type=code");
    expect(location).toContain("code_challenge_method=S256");

    const pkceCookie = response.cookies.get(PKCE_COOKIE_NAME);
    expect(pkceCookie).toBeDefined();
    const parsed = JSON.parse(pkceCookie!.value);
    expect(parsed.verifier).toBeTruthy();
    expect(parsed.state).toBeTruthy();
  });
});
