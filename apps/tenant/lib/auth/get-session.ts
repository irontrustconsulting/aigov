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
  // 60 s of expiry. Failure (Cognito unreachable, refresh token expired)
  // destroys the session and forces a re-login rather than forwarding a
  // guaranteed-to-fail token to the API.
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
      await sessionStore.destroy(sessionId);
      return null;
    }
  }

  await sessionStore.update(sessionId, { lastSeenAt: now });
  return session;
}
