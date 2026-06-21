import { cookies } from "next/headers";
import { sessionStore } from "./in-memory-session-store";
import { SESSION_COOKIE_NAME, IDLE_TIMEOUT_MS, ABSOLUTE_LIFETIME_MS } from "./constants";
import type { SessionData } from "./session-store";

/**
 * The full session validity check (idle + absolute lifetime), as opposed to
 * middleware's cheap cookie-presence-only check. Called from server
 * components and route handlers (notably the W4 BFF proxy route) that need
 * the actual stored token.
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

  await sessionStore.update(sessionId, { lastSeenAt: now });
  return session;
}
