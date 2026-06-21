import { useQuery, type UseQueryResult } from "@tanstack/react-query";
import type { LiveStateQueryKey } from "./query-keys";

/**
 * FE-7 / INV-25 / INV-32: the mandatory path for lifecycle/gate-vector/
 * coverage/authorisation reads. staleTime: 0 and refetchOnMount: "always"
 * are hardcoded — there is no options param to override them, so a call
 * site cannot accidentally cache a verdict across a transition. The
 * no-raw-live-state-query ESLint rule catches anyone who reaches around
 * this hook and calls useQuery directly against a live-state key.
 */
export function useLiveState<TData>(
  key: LiveStateQueryKey,
  fetcher: () => Promise<TData>
): UseQueryResult<TData> {
  return useQuery({
    queryKey: key,
    queryFn: fetcher,
    staleTime: 0,
    refetchOnMount: "always",
  });
}
