import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { useLiveState } from "../use-live-state";

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

describe("useLiveState", () => {
  test("fetches and hardcodes staleTime: 0 — there is no options param to override it", async () => {
    const fetcher = jest.fn().mockResolvedValue({ state: "AUTHORISED" });
    const { result } = renderHook(() => useLiveState(["lifecycle-state", "uc-1"], fetcher), {
      wrapper,
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual({ state: "AUTHORISED" });
    expect(fetcher).toHaveBeenCalledTimes(1);
  });
});
