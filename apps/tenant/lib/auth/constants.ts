export const SESSION_COOKIE_NAME = "irontrustai_tenant_session";
export const PKCE_COOKIE_NAME = "irontrustai_tenant_pkce";

export const IDLE_TIMEOUT_MS = 30 * 60 * 1000; // 30 minutes since last activity
export const ABSOLUTE_LIFETIME_MS = 12 * 60 * 60 * 1000; // 12 hours since login
export const PKCE_HANDSHAKE_MAX_AGE_S = 5 * 60; // 5 minutes to complete the redirect round-trip
