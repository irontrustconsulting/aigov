import { NextRequest } from "next/server";

jest.mock("@/lib/auth/get-session");

beforeAll(() => {
  process.env.API_BASE_URL = "https://api.internal.example";
});

afterEach(() => {
  jest.restoreAllMocks();
  jest.clearAllMocks();
});

function paramsFor(path: string[]) {
  return { params: Promise.resolve({ path }) };
}

describe("BFF proxy route", () => {
  test("forwards the request with the bearer ID token attached", async () => {
    const { getSession } = await import("@/lib/auth/get-session");
    (getSession as jest.Mock).mockResolvedValue({
      idToken: "the-id-token",
      refreshToken: "r",
      expiresAt: Date.now() + 1000,
      createdAt: Date.now(),
      lastSeenAt: Date.now(),
      userSub: "sub-1",
    });

    const fetchSpy = jest.spyOn(global, "fetch").mockResolvedValue({
      status: 200,
      text: async () => JSON.stringify({ ok: true }),
      headers: new Headers({ "content-type": "application/json" }),
    } as Response);

    const { GET } = await import("../route");
    const request = new NextRequest("http://localhost:3000/api/proxy/v1/me", {
      headers: { "sec-fetch-site": "same-origin" },
    });

    const response = await GET(request, paramsFor(["v1", "me"]));
    expect(response.status).toBe(200);

    const [calledUrl, init] = fetchSpy.mock.calls[0] as [string | URL, RequestInit];
    expect(String(calledUrl)).toBe("https://api.internal.example/v1/me");
    expect((init.headers as Record<string, string>).Authorization).toBe("Bearer the-id-token");
  });

  test("forwards If-Match on a mutation", async () => {
    const { getSession } = await import("@/lib/auth/get-session");
    (getSession as jest.Mock).mockResolvedValue({
      idToken: "the-id-token",
      refreshToken: "r",
      expiresAt: Date.now() + 1000,
      createdAt: Date.now(),
      lastSeenAt: Date.now(),
      userSub: "sub-1",
    });

    const fetchSpy = jest.spyOn(global, "fetch").mockResolvedValue({
      status: 200,
      text: async () => JSON.stringify({ ok: true }),
      headers: new Headers({ "content-type": "application/json" }),
    } as Response);

    const { PATCH } = await import("../route");
    const request = new NextRequest("http://localhost:3000/api/proxy/v1/use-cases/1", {
      method: "PATCH",
      headers: { "sec-fetch-site": "same-origin", "if-match": "3" },
      body: JSON.stringify({ name: "x" }),
    });

    await PATCH(request, paramsFor(["v1", "use-cases", "1"]));
    const [, init] = fetchSpy.mock.calls[0] as [string | URL, RequestInit];
    expect((init.headers as Record<string, string>)["If-Match"]).toBe("3");
  });

  test("passes through a 204 with no body instead of throwing", async () => {
    const { getSession } = await import("@/lib/auth/get-session");
    (getSession as jest.Mock).mockResolvedValue({
      idToken: "the-id-token",
      refreshToken: "r",
      expiresAt: Date.now() + 1000,
      createdAt: Date.now(),
      lastSeenAt: Date.now(),
      userSub: "sub-1",
    });

    jest.spyOn(global, "fetch").mockResolvedValue({
      status: 204,
      text: async () => "",
      headers: new Headers(),
    } as Response);

    const { GET } = await import("../route");
    const request = new NextRequest("http://localhost:3000/api/proxy/v1/draft-registrations/active", {
      headers: { "sec-fetch-site": "same-origin" },
    });

    const response = await GET(request, paramsFor(["v1", "draft-registrations", "active"]));
    expect(response.status).toBe(204);
  });

  test("401s when there is no session", async () => {
    const { getSession } = await import("@/lib/auth/get-session");
    (getSession as jest.Mock).mockResolvedValue(null);

    const { GET } = await import("../route");
    const request = new NextRequest("http://localhost:3000/api/proxy/v1/me", {
      headers: { "sec-fetch-site": "same-origin" },
    });

    const response = await GET(request, paramsFor(["v1", "me"]));
    expect(response.status).toBe(401);
  });

  test("403s a cross-origin mutation before checking the session", async () => {
    const { getSession } = await import("@/lib/auth/get-session");
    const { POST } = await import("../route");
    const request = new NextRequest("http://localhost:3000/api/proxy/v1/systems", {
      method: "POST",
      headers: { "sec-fetch-site": "cross-site" },
      body: JSON.stringify({}),
    });

    const response = await POST(request, paramsFor(["v1", "systems"]));
    expect(response.status).toBe(403);
    expect(getSession).not.toHaveBeenCalled();
  });
});
