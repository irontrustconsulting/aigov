/**
 * Server-side session store, keyed by an opaque session id. The browser
 * cookie carries only this id — never a token (INV-50, D-36, FE-2).
 */
export interface SessionData {
  /** The Cognito ID token — verify_cognito_token requires token_use=="id"
   * and reads custom:tenant_id/custom:role, which are ID-token-only claims
   * (FRONTEND.md §5/§6 correction, W8). */
  idToken: string;
  refreshToken: string;
  /** Epoch ms when the current idToken expires. */
  expiresAt: number;
  /** Epoch ms session was created — bounds the absolute lifetime. */
  createdAt: number;
  /** Epoch ms of the last authenticated request — bounds idle timeout. */
  lastSeenAt: number;
  /** Cognito `sub` — not used for authorization, just for diagnostics. */
  userSub: string;
}

export interface SessionStore {
  create(data: SessionData): Promise<string>;
  get(sessionId: string): Promise<SessionData | null>;
  update(sessionId: string, data: Partial<SessionData>): Promise<void>;
  destroy(sessionId: string): Promise<void>;
}
