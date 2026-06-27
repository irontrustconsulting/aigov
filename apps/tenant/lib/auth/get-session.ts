import { cookies } from "next/headers";
import { sessionStore } from "./in-memory-session-store";
import { refreshTokens } from "./cognito";
import { SESSION_COOKIE_NAME, IDLE_TIMEOUT_MS, ABSOLUTE_LIFETIME_MS } from "./constants";
import type { SessionData } from "./session-store";

/**
 * The full session validity check (idle + absolute lifetime), as opposed to
 * middleware's cheap cookie-presence-only check. Called from server
 * components and route handlers (notably the W4 BFF proxy route) that need
 * the actual stored token.
 *
 * Also performs a proactive Cognito token refresh when the stored idToken is
 * expired or within 60 s of expiry — prevents the proxy forwarding a stale
 * token to the API and receiving a 401 storm.
 */
export async function getSession(): Promise<SessionData | null> {
  const cookieStore = await cookies();
  const sessionId = cookieStore.get(SESSION_COOKIE_NAME)?.value;
  if (!sessionId) return null;

  const session = await sessionStore.get(sessionId);
  if (!session) return null;

  const now = Date.now();
  if (now - session.createdAt > ABSOLUTE_LIFETIME_MS) {
    await sessionStore.destroy(sessionId);
    return null;
  }
  if (now - session.lastSeenAt > IDLE_TIMEOUT_MS) {
    await sessionStore.destroy(sessionId);
    return null;
  }

  // Proactively refresh the Cognito token if it has expired or is within
  // 60 s of expiry. On failure (Cognito unreachable, refresh token expired,
  // empty refresh token) return the existing session unchanged — the API will
  // reject a truly expired token with 401, which the createQueryClient onError
  // handler already converts to a re-login. Destroying the session here causes
  // an infinite loop when the refresh itself fails.
  if (now >= session.expiresAt - 60_000) {
    try {
      const fresh = await refreshTokens(session.refreshToken);
      const refreshed: Partial<SessionData> = {
        idToken: fresh.id_token,
        expiresAt: now + fresh.expires_in * 1000,
        refreshToken: fresh.refresh_token ?? session.refreshToken,
        lastSeenAt: now,
      };
      await sessionStore.update(sessionId, refreshed);
      return { ...session, ...refreshed };
    } catch {
      // Refresh failed — return existing session unchanged. The API rejects a
      // truly expired token with 401, which createQueryClient converts to a
      // re-login. Destroying the session here causes an infinite redirect loop.
    }
  }

  await sessionStore.update(sessionId, { lastSeenAt: now });
  return session;
}
