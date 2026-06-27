/**
 * @jest-environment jsdom
 *
 * WI-3 done-check: every intake-wizard read and mutation hook calls only
 * this app's own BFF proxy (`/api/proxy/...`), never an absolute API origin
 * (INV-50, FE-9) — and none of them ever sets `If-Match` (FE-6 is dormant
 * for F1; no consumed route here accepts it).
 */
import { renderHook, waitFor, act } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import {
  useAffectedParties,
  useDataCategories,
  useEUSubcategories,
  useHostingModels,
  useHumanOversightTypes,
  useMe,
  useOperatorRoles,
  useOverrideClassification,
  usePreviewContext,
  useProductCategories,
  usePrefill,
  useRegister,
  useSubmitContext,
  useUsageContexts,
  useUseCaseLifecycle,
  useVendorsInCategory,
} from "../index";

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

function mockFetchOk(body: unknown = {}) {
  return jest.fn().mockResolvedValue({
    ok: true,
    status: 200,
    text: async () => JSON.stringify(body),
  } as Response);
}

afterEach(() => {
  jest.restoreAllMocks();
});

describe("intake hooks call only the BFF proxy, never the API directly", () => {
  test.each<[string, () => unknown]>([
    ["useProductCategories", () => useProductCategories()],
    ["useVendorsInCategory", () => useVendorsInCategory("cat-1")],
    ["useEUSubcategories", () => useEUSubcategories()],
    ["useOperatorRoles", () => useOperatorRoles()],
    ["useHostingModels", () => useHostingModels()],
    ["useUsageContexts", () => useUsageContexts()],
    ["useHumanOversightTypes", () => useHumanOversightTypes()],
    ["useDataCategories", () => useDataCategories()],
    ["useAffectedParties", () => useAffectedParties()],
    ["usePrefill", () => usePrefill("prod-1")],
    ["useMe", () => useMe()],
    ["useUseCaseLifecycle", () => useUseCaseLifecycle("uc-1")],
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

describe("intake mutation hooks call only the BFF proxy and never send If-Match", () => {
  test("useRegister invalidates the lifecycle live-state query on success", async () => {
    global.fetch = mockFetchOk({
      system: { id: "sys-1", name: "x", is_custom: true, catalogue_product: null, catalogue_vendor: null, owner_user_id: null, operator_role: null, hosting_model: null, lifecycle_stage: null, purpose: null, use_case_count: 0, use_case_lifecycle_states: [], created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z" },
      use_case: { id: "uc-1", tenant_id: "t1", system_id: "sys-1", title: "t", purpose: null, state: "intake", eu_tier: "unclassified", usage_context: null, human_oversight_type: null, data_categories: [], affected_parties: [] },
      classification: { id: "c1", use_case_id: "uc-1", tier: "minimal_risk", rationale: "r", version: 1, is_current: true, overridden: false, proposed_tier: null, basis_subcategory_code: null, basis_legal_ref: null, requires_context: false },
    });
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const invalidateSpy = jest.spyOn(client, "invalidateQueries");
    const { result } = renderHook(() => useRegister(), {
      wrapper: ({ children }) => <QueryClientProvider client={client}>{children}</QueryClientProvider>,
    });

    await act(async () => {
      result.current.mutate({
        name: "x", is_custom: true, catalogue_product_id: null, operator_role_id: null,
        hosting_model_id: null, lifecycle_stage: null, owner_user_id: null, purpose: null,
        title: "t", use_case_purpose: null, context_blob: {},
        usage_context_id: null, human_oversight_type_id: null,
        data_category_ids: [], affected_party_ids: [],
      });
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    const [url, init] = (global.fetch as jest.Mock).mock.calls[0] as [string, RequestInit];
    expect(url.startsWith("/api/proxy")).toBe(true);
    expect((init.headers as Record<string, string>)["If-Match"]).toBeUndefined();
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["lifecycle-state", "uc-1"] });
  });

  test("useOverrideClassification, usePreviewContext, useSubmitContext stay BFF-only", async () => {
    const fetchSpy = (global.fetch = mockFetchOk({}));

    const override = renderHook(() => useOverrideClassification("uc-1"), { wrapper });
    await act(async () => {
      override.result.current.mutate({ tier: "high_risk", subcategory_code: "c1", justification: null });
    });
    await waitFor(() => expect(override.result.current.isSuccess).toBe(true));

    const preview = renderHook(() => usePreviewContext("uc-1"), { wrapper });
    await act(async () => {
      preview.result.current.mutate({ answers: [], tree_version: "v1" });
    });
    await waitFor(() => expect(preview.result.current.isSuccess).toBe(true));

    const submit = renderHook(() => useSubmitContext("uc-1"), { wrapper });
    await act(async () => {
      submit.result.current.mutate({
        answers: [],
        tree_version: "v1",
        override_tier: null,
        justification: null,
      });
    });
    await waitFor(() => expect(submit.result.current.isSuccess).toBe(true));

    for (const call of fetchSpy.mock.calls) {
      const [url, init] = call as [string, RequestInit];
      expect(url.startsWith("/api/proxy")).toBe(true);
      expect((init.headers as Record<string, string>)["If-Match"]).toBeUndefined();
    }
  });
});
