import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import { isSameOriginRequest } from "@/lib/auth/csrf";
import { sessionStore } from "@/lib/auth/in-memory-session-store";
import { SESSION_COOKIE_NAME } from "@/lib/auth/constants";
import { refreshTokens } from "@/lib/auth/cognito";

export async function POST(request: NextRequest) {
  if (!isSameOriginRequest(request)) {
    return NextResponse.json({ error: "Cross-origin request rejected" }, { status: 403 });
  }

  const sessionId = request.cookies.get(SESSION_COOKIE_NAME)?.value;
  if (!sessionId) {
    return NextResponse.json({ error: "No session" }, { status: 401 });
  }

  const session = await sessionStore.get(sessionId);
  if (!session) {
    return NextResponse.json({ error: "No session" }, { status: 401 });
  }

  const tokens = await refreshTokens(session.refreshToken);
  const now = Date.now();
  await sessionStore.update(sessionId, {
    idToken: tokens.id_token,
    // Cognito does not always reissue a refresh_token on refresh; keep the
    // existing one unless a new one is returned.
    refreshToken: tokens.refresh_token ?? session.refreshToken,
    expiresAt: now + tokens.expires_in * 1000,
    lastSeenAt: now,
  });

  return NextResponse.json({ ok: true });
}
