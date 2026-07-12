import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import { isSameOriginRequest } from "@/lib/auth/csrf";
import { sessionStore } from "@/lib/auth/in-memory-session-store";
import { SESSION_COOKIE_NAME } from "@/lib/auth/constants";
import { buildLogoutUrl } from "@/lib/auth/cognito";

export async function POST(request: NextRequest) {
  if (!isSameOriginRequest(request)) {
    return NextResponse.json({ error: "Cross-origin request rejected" }, { status: 403 });
  }

  const sessionId = request.cookies.get(SESSION_COOKIE_NAME)?.value;
  if (sessionId) {
    await sessionStore.destroy(sessionId);
  }

  // Also clear Cognito's own SSO cookie (via its hosted-UI /logout endpoint) —
  // destroying only the local session leaves Cognito's SSO session alive, so
  // the very next /api/auth/login silently re-authenticates with no prompt.
  const response = NextResponse.json({ ok: true, redirectTo: buildLogoutUrl() });
  response.cookies.delete(SESSION_COOKIE_NAME);
  return response;
}
