import type { NextRequest } from "next/server";
import { authEnv } from "./env";

/**
 * CSRF guard for state-changing BFF routes (FE-2): SameSite=Lax alone is not
 * the whole defence (it still allows top-level cross-site GET navigations
 * and some legacy browsers don't enforce it), so every state-changing route
 * also checks Sec-Fetch-Site / Origin explicitly.
 *
 * Duplicated per app (not shared via a package) — same rule as the rest of
 * the auth plane: auth-adjacent code is never shared between planes (FE-1).
 */
export function isSameOriginRequest(request: NextRequest): boolean {
  const secFetchSite = request.headers.get("sec-fetch-site");
  if (secFetchSite) {
    // Modern browsers send this on every request; "same-origin" is the only
    // acceptable value for a state-changing same-origin BFF route.
    return secFetchSite === "same-origin";
  }

  // Fallback for clients that don't send Sec-Fetch-Site: compare Origin (or
  // Referer as a last resort) against this app's own origin.
  const origin = request.headers.get("origin") ?? request.headers.get("referer");
  if (!origin) return false;
  return origin.startsWith(authEnv.appOrigin);
}
