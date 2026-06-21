import { QueryClient } from "@tanstack/react-query";

/**
 * Shared default config for both apps' QueryClient — each app instantiates
 * its own client (FE-9 ties TanStack Query to "fetching through that app's
 * own BFF"), but the defaults should never diverge. This is contract/config
 * sharing, not auth sharing, so it doesn't breach the FE-1 package boundary.
 */
export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        // Live-state reads override this per-query via useLiveState
        // (staleTime: 0); this is the default for ordinary reads only.
        staleTime: 30 * 1000,
        retry: 1,
      },
    },
  });
}
