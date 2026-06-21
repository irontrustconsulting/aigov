import { NextRequest } from "next/server";
import { middleware } from "../middleware";
import { SESSION_COOKIE_NAME } from "@/lib/auth/constants";

describe("middleware", () => {
  test("unauthenticated hit on a protected route redirects to login", () => {
    const request = new NextRequest("http://localhost:3000/dashboard");
    const response = middleware(request);
    expect(response.status).toBe(307);
    expect(response.headers.get("location")).toContain("/api/auth/login");
  });

  test("a request carrying the session cookie passes through", () => {
    const request = new NextRequest("http://localhost:3000/dashboard", {
      headers: { cookie: `${SESSION_COOKIE_NAME}=some-opaque-id` },
    });
    const response = middleware(request);
    // NextResponse.next() carries no redirect Location.
    expect(response.headers.get("location")).toBeNull();
  });
});
