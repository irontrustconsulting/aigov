/**
 * @jest-environment jsdom
 *
 * INV-53 — export/ATO-document hooks MUST NOT fire on mount or window focus.
 * Only coverage hooks may fire on mount (they stage no audit event).
 * No require_evidence_for_satisfied param in any coverage URL (N1 — server-internal).
 */
import { renderHook, act, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import {
  useTenantCoverage,
  useSystemCoverage,
  useUseCaseCoverage,
  useSystemExport,
  useUseCaseExport,
  useFrameworkExport,
  useAtoDocument,
} from "../queries";
import type { CoverageMatrixRead } from "@irontrust/api-client";

function makeWrapper() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
  };
}

const mockMatrix: CoverageMatrixRead = {
  scope: "tenant",
  scope_id: null,
  framework_filter: null,
  include_unapproved: false,
  controls: [],
  frameworks: [],
  unaddressed_controls: [],
  not_an_obligation_set: true,
  generated_at: "2026-06-22T12:00:00Z",
};

function fetchedUrls(): string[] {
  return (global.fetch as jest.Mock).mock.calls.map(([url]: [RequestInfo | URL]) => String(url));
}

function mockFetchOk(body: unknown = mockMatrix) {
  global.fetch = jest.fn(() =>
    Promise.resolve({ ok: true, status: 200, text: async () => JSON.stringify(body) } as Response)
  ) as jest.Mock;
}

afterEach(() => jest.restoreAllMocks());

describe("Coverage hooks (eager, staleTime: 0)", () => {
  test("useTenantCoverage fires on mount", async () => {
    mockFetchOk();
    const { result } = renderHook(() => useTenantCoverage(), { wrapper: makeWrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(fetchedUrls().filter((u) => u.includes("/v1/coverage"))).toHaveLength(1);
  });

  test("useTenantCoverage: no require_evidence_for_satisfied in URL (N1)", async () => {
    mockFetchOk();
    const { result } = renderHook(() => useTenantCoverage(), { wrapper: makeWrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    const urls = fetchedUrls();
    expect(urls.some((u) => u.includes("require_evidence_for_satisfied"))).toBe(false);
  });

  test("useSystemCoverage fires on mount when systemId provided", async () => {
    mockFetchOk();
    const { result } = renderHook(() => useSystemCoverage("sys-1"), { wrapper: makeWrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(fetchedUrls().filter((u) => u.includes("/v1/systems/sys-1/coverage"))).toHaveLength(1);
  });

  test("useUseCaseCoverage fires on mount when assessmentId provided", async () => {
    mockFetchOk();
    const { result } = renderHook(() => useUseCaseCoverage("ass-1"), { wrapper: makeWrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(fetchedUrls().filter((u) => u.includes("/v1/assessments/ass-1/coverage"))).toHaveLength(1);
  });
});

describe("Export hooks (deliberate-only — INV-53)", () => {
  test("useSystemExport does NOT fire on mount (enabled: false)", async () => {
    mockFetchOk({});
    renderHook(() => useSystemExport("sys-1", false), { wrapper: makeWrapper() });
    // Flush microtasks
    await act(async () => { await Promise.resolve(); });
    const exportCalls = fetchedUrls().filter((u) => u.includes("/export"));
    expect(exportCalls).toHaveLength(0);
  });

  test("useSystemExport does NOT re-fire on window focus", async () => {
    mockFetchOk({});
    renderHook(() => useSystemExport("sys-1", false), { wrapper: makeWrapper() });
    await act(async () => { window.dispatchEvent(new Event("focus")); await Promise.resolve(); });
    expect(fetchedUrls().filter((u) => u.includes("/export"))).toHaveLength(0);
  });

  test("useUseCaseExport does NOT fire on mount (enabled: false)", async () => {
    mockFetchOk({});
    renderHook(() => useUseCaseExport("uc-1", false), { wrapper: makeWrapper() });
    await act(async () => { await Promise.resolve(); });
    expect(fetchedUrls().filter((u) => u.includes("/export"))).toHaveLength(0);
  });

  test("useFrameworkExport does NOT fire on mount (enabled: false)", async () => {
    mockFetchOk({});
    renderHook(() => useFrameworkExport("ISO_42001", false), { wrapper: makeWrapper() });
    await act(async () => { await Promise.resolve(); });
    expect(fetchedUrls().filter((u) => u.includes("/export"))).toHaveLength(0);
  });

  test("useAtoDocument does NOT fire on mount (enabled: false)", async () => {
    mockFetchOk({});
    renderHook(() => useAtoDocument("uc-1", false), { wrapper: makeWrapper() });
    await act(async () => { await Promise.resolve(); });
    expect(fetchedUrls().filter((u) => u.includes("/authorisation/document"))).toHaveLength(0);
  });

  test("useSystemExport DOES fire when enabled: true", async () => {
    mockFetchOk({ system_id: "sys-1", system: {}, use_cases: [], system_coverage: mockMatrix, audit_trail: [], generated_at: "2026-06-22T12:00:00Z", content_hash: "abc" });
    const { result } = renderHook(() => useSystemExport("sys-1", true), { wrapper: makeWrapper() });
    await waitFor(() => !result.current.isLoading);
    expect(fetchedUrls().filter((u) => u.includes("/systems/sys-1/export"))).toHaveLength(1);
  });
});
