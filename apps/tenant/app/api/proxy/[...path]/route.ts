import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import { getSession } from "@/lib/auth/get-session";
import { isSameOriginRequest } from "@/lib/auth/csrf";
import { SESSION_COOKIE_NAME } from "@/lib/auth/constants";

const STATE_CHANGING_METHODS = new Set(["POST", "PUT", "PATCH", "DELETE"]);

/**
 * The BFF proxy (FE-9): every browser→API call rides through here. Holds
 * the Cognito ID token server-side and forwards it as the bearer
 * (FRONTEND.md §5/§6 — corrected to ID token, since verify_cognito_token
 * requires token_use=="id"). The browser never sees the token (INV-50).
 */
async function handle(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
): Promise<NextResponse> {
  if (STATE_CHANGING_METHODS.has(request.method) && !isSameOriginRequest(request)) {
    return NextResponse.json({ error: "Cross-origin request rejected" }, { status: 403 });
  }

  const session = await getSession();
  if (!session) {
    // Clear any stale session cookie so the browser isn't stuck in a
    // redirect loop (stale cookie survives a server restart, blocking
    // re-login until the browser cookie jar is manually cleared).
    const res = NextResponse.json({ error: "Not authenticated" }, { status: 401 });
    res.cookies.delete(SESSION_COOKIE_NAME);
    return res;
  }

  const { path } = await params;
  const apiBaseUrl = process.env.API_BASE_URL;
  if (!apiBaseUrl) {
    throw new Error("Missing required env var API_BASE_URL");
  }

  const url = new URL(`${apiBaseUrl}/${path.join("/")}`);
  url.search = new URL(request.url).search;

  const headers: Record<string, string> = {
    Authorization: `Bearer ${session.idToken}`,
  };
  const incomingContentType = request.headers.get("content-type");
  if (incomingContentType) headers["Content-Type"] = incomingContentType;
  const ifMatch = request.headers.get("if-match");
  if (ifMatch) headers["If-Match"] = ifMatch;

  const hasBody = !["GET", "HEAD"].includes(request.method);

  const apiResponse = await fetch(url, {
    method: request.method,
    headers,
    body: hasBody ? await request.text() : undefined,
  });

  const responseBody = await apiResponse.text();
  return new NextResponse(responseBody, {
    status: apiResponse.status,
    headers: {
      "Content-Type": apiResponse.headers.get("content-type") ?? "application/json",
    },
  });
}

export {
  handle as GET,
  handle as POST,
  handle as PATCH,
  handle as PUT,
  handle as DELETE,
};
