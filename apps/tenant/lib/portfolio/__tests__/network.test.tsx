/**
 * @jest-environment jsdom
 *
 * Every portfolio read hook calls only this app's own BFF proxy
 * (`/api/proxy/...`), never an absolute API origin (INV-50, FE-9), and none
 * of them ever sets `If-Match` (FE-6 is dormant for F2; none of its routes
 * accept it).
 */
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { usePortfolio, useSystemRollup, useSystems } from "../queries";

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

function mockFetchOk(body: unknown = []) {
  return jest.fn().mockResolvedValue({
    ok: true,
    status: 200,
    text: async () => JSON.stringify(body),
  } as Response);
}

afterEach(() => {
  jest.restoreAllMocks();
});

describe("portfolio hooks call only the BFF proxy, never the API directly", () => {
  test.each<[string, () => unknown]>([
    ["usePortfolio", () => usePortfolio()],
    ["useSystemRollup", () => useSystemRollup("sys-1")],
    ["useSystems", () => useSystems()],
  ])("%s", async (_name, hook) => {
    const fetchSpy = (global.fetch = mockFetchOk([]));

    const { result } = renderHook(hook, { wrapper });
    await waitFor(() => {
      const r = result.current as { isLoading: boolean };
      expect(r.isLoading).toBe(false);
    });

    expect(fetchSpy).toHaveBeenCalled();
    for (const call of fetchSpy.mock.calls) {
      const [url, init] = call as [string, RequestInit | undefined];
      expect(url.startsWith("/api/proxy")).toBe(true);
      expect((init?.headers as Record<string, string> | undefined)?.["If-Match"]).toBeUndefined();
    }
  });
});
