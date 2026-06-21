import { NextResponse } from "next/server";
import { generateCodeVerifier, generateCodeChallenge, generateState } from "@/lib/auth/pkce";
import { buildAuthorizeUrl } from "@/lib/auth/cognito";
import { PKCE_COOKIE_NAME, PKCE_HANDSHAKE_MAX_AGE_S } from "@/lib/auth/constants";

export async function GET() {
  const verifier = generateCodeVerifier();
  const challenge = generateCodeChallenge(verifier);
  const state = generateState();

  const response = NextResponse.redirect(buildAuthorizeUrl(state, challenge));

  // Short-lived, distinct from the session cookie — only needs to survive
  // the redirect round-trip to Cognito and back (FE-2).
  response.cookies.set(PKCE_COOKIE_NAME, JSON.stringify({ verifier, state }), {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge: PKCE_HANDSHAKE_MAX_AGE_S,
  });

  return response;
}
