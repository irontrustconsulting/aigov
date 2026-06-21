import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import { SESSION_COOKIE_NAME } from "@/lib/auth/constants";

/**
 * Protected-route gating (FE-2). Cheap cookie-presence check only — full
 * validity (idle/absolute timeout, store lookup) happens in
 * lib/auth/get-session.ts, called from server components and route handlers
 * that need the actual token (notably the W4 BFF proxy route).
 */
export function middleware(request: NextRequest) {
  const hasSession = request.cookies.has(SESSION_COOKIE_NAME);
  if (!hasSession) {
    const loginUrl = new URL("/api/auth/login", request.url);
    return NextResponse.redirect(loginUrl);
  }
  return NextResponse.next();
}

export const config = {
  matcher: [
    /*
     * Match all paths except:
     *  - /api/auth/* (must stay reachable unauthenticated)
     *  - Next internals and static assets
     */
    "/((?!api/auth|_next/static|_next/image|favicon.ico).*)",
  ],
};
