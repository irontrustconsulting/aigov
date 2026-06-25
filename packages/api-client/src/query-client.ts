import { QueryClient, QueryCache } from "@tanstack/react-query";
import { ApiError } from "./errors";

/**
 * Shared default config for both apps' QueryClient — each app instantiates
 * its own client (FE-9 ties TanStack Query to "fetching through that app's
 * own BFF"), but the defaults should never diverge. This is contract/config
 * sharing, not auth sharing, so it doesn't breach the FE-1 package boundary.
 */
export function createQueryClient(): QueryClient {
  return new QueryClient({
    queryCache: new QueryCache({
      onError(error) {
        // 401 means the session cookie exists but the server-side store no
        // longer holds it (e.g. after a dev-server restart). Redirect to
        // login rather than showing a generic error — the user's cookie is
        // stale, not their fault.
        if (error instanceof ApiError && error.status === 401 && typeof window !== "undefined") {
          window.location.href = "/api/auth/login";
        }
      },
    }),
    defaultOptions: {
      queries: {
        // Live-state reads override this per-query via useLiveState
        // (staleTime: 0); this is the default for ordinary reads only.
        staleTime: 30 * 1000,
        retry(failureCount, error) {
          // Never retry a 401 — the session is gone; the redirect above fires.
          if (error instanceof ApiError && error.status === 401) return false;
          return failureCount < 1;
        },
      },
    },
  });
}
