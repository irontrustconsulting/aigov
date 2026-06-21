/**
 * Runtime defence-in-depth (FE-9, INV-3, INV-13): tenant_id is always
 * server-resolved from token/context, never client-supplied; provenance is
 * always server-derived, never client-authored. Compile-time types omit
 * these fields entirely from every mutation body type — this is the runtime
 * backstop for values that arrive via `as any`, a spread, or external data,
 * where the type system can't help.
 */
const FORBIDDEN_KEYS = new Set(["tenant_id", "provenance"]);

export class ForbiddenFieldError extends Error {
  constructor(key: string) {
    super(`Request body must not contain "${key}" — it is always server-resolved/derived.`);
    this.name = "ForbiddenFieldError";
  }
}

function findForbiddenKey(value: unknown, seen = new Set<unknown>()): string | null {
  if (value === null || typeof value !== "object") return null;
  if (seen.has(value)) return null;
  seen.add(value);

  if (Array.isArray(value)) {
    for (const item of value) {
      const found = findForbiddenKey(item, seen);
      if (found) return found;
    }
    return null;
  }

  for (const [key, nested] of Object.entries(value as Record<string, unknown>)) {
    if (FORBIDDEN_KEYS.has(key)) return key;
    const found = findForbiddenKey(nested, seen);
    if (found) return found;
  }
  return null;
}

/** Throws before the request is sent if the body contains a forbidden key
 * anywhere (top-level or nested). */
export function assertNoForbiddenFields(body: unknown): void {
  const found = findForbiddenKey(body);
  if (found) {
    throw new ForbiddenFieldError(found);
  }
}
