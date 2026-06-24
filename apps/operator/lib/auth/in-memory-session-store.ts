import { randomUUID } from "node:crypto";
import type { SessionData, SessionStore } from "./session-store";

/**
 * MVP session store (Appendix A, sprints/UI-F0-FOUNDATION.md): a
 * module-scoped Map.
 *
 * DEV-ONLY — NOT MULTI-INSTANCE-SAFE. This store lives in the Node process
 * memory of a single Next server instance. It breaks refresh-token
 * continuity and horizontal scaling the moment more than one instance runs
 * (a session created on instance A is invisible to instance B, including
 * across a single instance's restart/redeploy). The production shape is a
 * shared store — Redis, or a platform-plane session table — deferred per
 * Appendix A; do not build it as part of F0.
 */
class InMemorySessionStore implements SessionStore {
  private sessions = new Map<string, SessionData>();

  async create(data: SessionData): Promise<string> {
    const id = randomUUID();
    this.sessions.set(id, data);
    return id;
  }

  async get(sessionId: string): Promise<SessionData | null> {
    return this.sessions.get(sessionId) ?? null;
  }

  async update(sessionId: string, data: Partial<SessionData>): Promise<void> {
    const existing = this.sessions.get(sessionId);
    if (!existing) return;
    this.sessions.set(sessionId, { ...existing, ...data });
  }

  async destroy(sessionId: string): Promise<void> {
    this.sessions.delete(sessionId);
  }
}

// Pin to globalThis so Next.js HMR module re-instantiation in dev doesn't
// wipe the Map. In production there is no HMR; this is a no-op there.
declare global {
  // eslint-disable-next-line no-var
  var __irontrustSessionStore: InMemorySessionStore | undefined;
}

export const sessionStore: SessionStore =
  globalThis.__irontrustSessionStore ??
  (globalThis.__irontrustSessionStore = new InMemorySessionStore());
