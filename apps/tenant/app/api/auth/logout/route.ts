import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import { isSameOriginRequest } from "@/lib/auth/csrf";
import { sessionStore } from "@/lib/auth/in-memory-session-store";
import { SESSION_COOKIE_NAME } from "@/lib/auth/constants";

export async function POST(request: NextRequest) {
  if (!isSameOriginRequest(request)) {
    return NextResponse.json({ error: "Cross-origin request rejected" }, { status: 403 });
  }

  const sessionId = request.cookies.get(SESSION_COOKIE_NAME)?.value;
  if (sessionId) {
    await sessionStore.destroy(sessionId);
  }

  const response = NextResponse.json({ ok: true, redirectTo: "/" });
  response.cookies.delete(SESSION_COOKIE_NAME);
  return response;
}
