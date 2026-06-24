import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import { exchangeCodeForTokens, decodeSub } from "@/lib/auth/cognito";
import { sessionStore } from "@/lib/auth/in-memory-session-store";
import { PKCE_COOKIE_NAME, SESSION_COOKIE_NAME, ABSOLUTE_LIFETIME_MS } from "@/lib/auth/constants";
import { authEnv } from "@/lib/auth/env";

export async function GET(request: NextRequest) {
  const url = new URL(request.url);
  const code = url.searchParams.get("code");
  const returnedState = url.searchParams.get("state");

  const pkceCookie = request.cookies.get(PKCE_COOKIE_NAME)?.value;

  const fail = (reason: string) => {
    const res = NextResponse.json({ error: reason }, { status: 400 });
    res.cookies.delete(PKCE_COOKIE_NAME);
    return res;
  };

  if (!code || !returnedState) return fail("Missing code or state");
  if (!pkceCookie) return fail("Missing PKCE handshake cookie");

  let verifier: string;
  let expectedState: string;
  try {
    ({ verifier, state: expectedState } = JSON.parse(pkceCookie));
  } catch {
    return fail("Malformed PKCE handshake cookie");
  }

  if (returnedState !== expectedState) return fail("State mismatch");

  const tokens = await exchangeCodeForTokens(code, verifier);
  const now = Date.now();
  const sessionId = await sessionStore.create({
    idToken: tokens.id_token,
    refreshToken: tokens.refresh_token ?? "",
    expiresAt: now + tokens.expires_in * 1000,
    createdAt: now,
    lastSeenAt: now,
    userSub: decodeSub(tokens.id_token),
  });

  const response = NextResponse.redirect(new URL("/dashboard", authEnv.appOrigin));
  response.cookies.delete(PKCE_COOKIE_NAME);
  response.cookies.set(SESSION_COOKIE_NAME, sessionId, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge: ABSOLUTE_LIFETIME_MS / 1000,
  });
  return response;
}
