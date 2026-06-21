export interface ApiClientOptions {
  /** Relative path under the calling app's own BFF proxy — never an absolute
   * API origin URL (FE-9: the client calls only the app's BFF, never the API
   * directly). E.g. "/api/proxy". */
  baseUrl: string;
}

export interface RequestOptions {
  /** Sent as If-Match on mutations carrying a lock_version (FE-6, PAT-6,
   * INV-14). */
  lockVersion?: string;
  signal?: AbortSignal;
}

/** Excludes tenant_id/provenance from every mutation body type at the
 * compile-time layer (FE-9, INV-3, INV-13) — the runtime guard in guards.ts
 * is the backstop for values that arrive via `as any`/spread/external data. */
export type MutationBody<T> = Omit<T, "tenant_id" | "provenance">;
