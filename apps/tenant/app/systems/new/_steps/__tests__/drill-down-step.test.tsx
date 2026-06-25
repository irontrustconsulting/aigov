/**
 * @jest-environment jsdom
 */
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { DrillDownStep, type DrillDownResult } from "../drill-down-step";

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

/**
 * Mock that routes by URL path + query:
 *   product-categories (no parent_id)  → top-level categories
 *   product-categories?parent_id=xxx   → sub-categories
 *   {catId}/vendors                    → vendors
 *   {catId}/products                   → products
 *   products/{id}                      → product detail
 */
function mockFetchByPath(map: Record<string, unknown>) {
  global.fetch = jest.fn((input: RequestInfo | URL) => {
    const full = String(input);
    const [pathname, queryStr = ""] = full.split("?");
    const params = new URLSearchParams(queryStr);
    const segments = pathname.split("/").filter(Boolean);
    const last = segments[segments.length - 1];
    const v1At = segments.indexOf("v1");
    const resource = segments[v1At + 2];

    let key: string | undefined;
    if (last === "vendors") key = "vendors";
    else if (last === "products" && resource !== "products") key = "products";
    else if (resource === "products") key = `products/${last}`; // detail
    else if (resource === "product-categories") {
      const parentId = params.get("parent_id");
      key = parentId ? `sub-categories:${parentId}` : "top-categories";
    }

    return Promise.resolve({
      ok: true,
      status: 200,
      text: async () => JSON.stringify(key && key in map ? map[key] : []),
    } as Response);
  }) as jest.Mock;
}

afterEach(() => {
  jest.restoreAllMocks();
});

describe("DrillDownStep", () => {
  // ── Empty / exit ─────────────────────────────────────────────────────────────

  test("renders cleanly with an empty taxonomy and offers the custom exit", async () => {
    mockFetchByPath({ "top-categories": [] });
    render(<DrillDownStep onComplete={jest.fn()} />, { wrapper });

    await waitFor(() =>
      expect(screen.getByText(/no categories available/i)).toBeInTheDocument()
    );
    expect(screen.getByRole("button", { name: /not in catalogue/i })).toBeInTheDocument();
  });

  test("the custom branch carries isCustom=true and no product forward", async () => {
    mockFetchByPath({ "top-categories": [] });
    const onComplete = jest.fn<void, [DrillDownResult]>();

    render(<DrillDownStep onComplete={onComplete} />, { wrapper });

    await waitFor(() => screen.getByRole("button", { name: /not in catalogue/i }));
    fireEvent.click(screen.getByRole("button", { name: /not in catalogue/i }));

    expect(onComplete).toHaveBeenCalledWith({
      isCustom: true,
      catalogueProductId: null,
      catalogueProductName: null,
    });
  });

  // ── Full funnel — single vendor (auto-skip) ───────────────────────────────

  test("single-vendor auto-skip: drilling top → sub → product → confirm", async () => {
    mockFetchByPath({
      "top-categories": [
        { id: "top-1", code: "COMMS", name: "Communications", description: null, parent_id: null },
      ],
      "sub-categories:top-1": [
        { id: "sub-1", code: "COMMS_BOT", name: "Chatbots", description: null, parent_id: "top-1" },
      ],
      vendors: [{ id: "v1", name: "Acme", logo_url: null }],
      products: [{ id: "p1", name: "Acme Bot", vendor_id: "v1", logo_url: null }],
      "products/p1": {
        id: "p1",
        name: "Acme Bot",
        logo_url: null,
        vendor: { id: "v1", name: "Acme", logo_url: null },
        categories: [],
        eu_ai_act_subcategories: [],
      },
    });
    const onComplete = jest.fn<void, [DrillDownResult]>();

    render(<DrillDownStep onComplete={onComplete} />, { wrapper });

    // Stage 1: top-level
    await waitFor(() => screen.getByText("Communications"));
    fireEvent.click(screen.getByRole("button", { name: /communications/i }));

    // Stage 2: sub-category
    await waitFor(() => screen.getByText("Chatbots"));
    fireEvent.click(screen.getByRole("button", { name: /chatbots/i }));

    // Vendor auto-skip fires → product rung appears directly
    await waitFor(() => screen.getByText("Acme Bot"));
    fireEvent.click(screen.getByRole("button", { name: /Acme Bot/i }));

    // Confirm stage
    await waitFor(() => screen.getByRole("button", { name: /use this product/i }));
    fireEvent.click(screen.getByRole("button", { name: /use this product/i }));

    expect(onComplete).toHaveBeenCalledWith({
      isCustom: false,
      catalogueProductId: "p1",
      catalogueProductName: "Acme Bot",
    });
  });

  // ── Full funnel — multi vendor ────────────────────────────────────────────

  test("multi-vendor: shows vendor rung and filters to products of chosen vendor", async () => {
    mockFetchByPath({
      "top-categories": [
        { id: "top-1", code: "COMMS", name: "Communications", description: null, parent_id: null },
      ],
      "sub-categories:top-1": [
        { id: "sub-1", code: "COMMS_BOT", name: "Chatbots", description: null, parent_id: "top-1" },
      ],
      vendors: [
        { id: "v1", name: "Acme", logo_url: null },
        { id: "v2", name: "Beta AI", logo_url: null },
      ],
      products: [{ id: "p2", name: "Beta Bot", vendor_id: "v2", logo_url: null }],
      "products/p2": {
        id: "p2",
        name: "Beta Bot",
        logo_url: null,
        vendor: { id: "v2", name: "Beta AI", logo_url: null },
        categories: [],
        eu_ai_act_subcategories: [],
      },
    });
    const onComplete = jest.fn<void, [DrillDownResult]>();

    render(<DrillDownStep onComplete={onComplete} />, { wrapper });

    await waitFor(() => screen.getByText("Communications"));
    fireEvent.click(screen.getByRole("button", { name: /communications/i }));

    await waitFor(() => screen.getByText("Chatbots"));
    fireEvent.click(screen.getByRole("button", { name: /chatbots/i }));

    // Vendor rung visible (2 vendors → no auto-skip)
    await waitFor(() => screen.getByText("Beta AI"));
    expect(screen.getByText("Acme")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /beta ai/i }));

    // Product rung for Beta AI
    await waitFor(() => screen.getByText("Beta Bot"));
    fireEvent.click(screen.getByRole("button", { name: /beta bot/i }));

    // Confirm
    await waitFor(() => screen.getByRole("button", { name: /use this product/i }));
    fireEvent.click(screen.getByRole("button", { name: /use this product/i }));

    expect(onComplete).toHaveBeenCalledWith({
      isCustom: false,
      catalogueProductId: "p2",
      catalogueProductName: "Beta Bot",
    });
  });

  // ── Back navigation ───────────────────────────────────────────────────────

  test("back from sub-category rung returns to top-level", async () => {
    mockFetchByPath({
      "top-categories": [
        { id: "top-1", code: "COMMS", name: "Communications", description: null, parent_id: null },
      ],
      "sub-categories:top-1": [
        { id: "sub-1", code: "COMMS_BOT", name: "Chatbots", description: null, parent_id: "top-1" },
      ],
      vendors: [],
    });

    render(<DrillDownStep onComplete={jest.fn()} />, { wrapper });

    await waitFor(() => screen.getByText("Communications"));
    fireEvent.click(screen.getByRole("button", { name: /communications/i }));
    await waitFor(() => screen.getByText("Chatbots"));

    fireEvent.click(screen.getByRole("button", { name: /← back/i }));
    await waitFor(() => screen.getByText("Communications"));
    expect(screen.queryByText("Chatbots")).not.toBeInTheDocument();
  });

  // ── In-house exit at every rung ───────────────────────────────────────────

  test("in-house exit from sub-category rung yields isCustom=true", async () => {
    mockFetchByPath({
      "top-categories": [
        { id: "top-1", code: "COMMS", name: "Communications", description: null, parent_id: null },
      ],
      "sub-categories:top-1": [
        { id: "sub-1", code: "COMMS_BOT", name: "Chatbots", description: null, parent_id: "top-1" },
      ],
      vendors: [],
    });
    const onComplete = jest.fn<void, [DrillDownResult]>();

    render(<DrillDownStep onComplete={onComplete} />, { wrapper });

    await waitFor(() => screen.getByText("Communications"));
    fireEvent.click(screen.getByRole("button", { name: /communications/i }));
    await waitFor(() => screen.getByText("Chatbots"));

    fireEvent.click(screen.getByRole("button", { name: /not in catalogue/i }));
    expect(onComplete).toHaveBeenCalledWith({
      isCustom: true,
      catalogueProductId: null,
      catalogueProductName: null,
    });
  });

  test("in-house exit from vendor rung yields isCustom=true", async () => {
    mockFetchByPath({
      "top-categories": [
        { id: "top-1", code: "COMMS", name: "Communications", description: null, parent_id: null },
      ],
      "sub-categories:top-1": [
        { id: "sub-1", code: "COMMS_BOT", name: "Chatbots", description: null, parent_id: "top-1" },
      ],
      vendors: [
        { id: "v1", name: "Acme", logo_url: null },
        { id: "v2", name: "Beta AI", logo_url: null },
      ],
    });
    const onComplete = jest.fn<void, [DrillDownResult]>();

    render(<DrillDownStep onComplete={onComplete} />, { wrapper });

    await waitFor(() => screen.getByText("Communications"));
    fireEvent.click(screen.getByRole("button", { name: /communications/i }));
    await waitFor(() => screen.getByText("Chatbots"));
    fireEvent.click(screen.getByRole("button", { name: /chatbots/i }));
    await waitFor(() => screen.getByText("Acme"));

    fireEvent.click(screen.getByRole("button", { name: /not in catalogue/i }));
    expect(onComplete).toHaveBeenCalledWith({
      isCustom: true,
      catalogueProductId: null,
      catalogueProductName: null,
    });
  });

  // ── INV-70 states ─────────────────────────────────────────────────────────

  test("empty vendor list shows EmptyState with in-house exit", async () => {
    mockFetchByPath({
      "top-categories": [
        { id: "top-1", code: "COMMS", name: "Communications", description: null, parent_id: null },
      ],
      "sub-categories:top-1": [
        { id: "sub-1", code: "COMMS_BOT", name: "Chatbots", description: null, parent_id: "top-1" },
      ],
      vendors: [],
    });

    render(<DrillDownStep onComplete={jest.fn()} />, { wrapper });

    await waitFor(() => screen.getByText("Communications"));
    fireEvent.click(screen.getByRole("button", { name: /communications/i }));
    await waitFor(() => screen.getByText("Chatbots"));
    fireEvent.click(screen.getByRole("button", { name: /chatbots/i }));

    await waitFor(() =>
      expect(screen.getByText(/no vendors available/i)).toBeInTheDocument()
    );
    expect(screen.getByRole("button", { name: /not in catalogue/i })).toBeInTheDocument();
  });

  test("empty product list shows EmptyState with in-house exit", async () => {
    mockFetchByPath({
      "top-categories": [
        { id: "top-1", code: "COMMS", name: "Communications", description: null, parent_id: null },
      ],
      "sub-categories:top-1": [
        { id: "sub-1", code: "COMMS_BOT", name: "Chatbots", description: null, parent_id: "top-1" },
      ],
      vendors: [
        { id: "v1", name: "Acme", logo_url: null },
        { id: "v2", name: "Beta AI", logo_url: null },
      ],
      products: [],
    });

    render(<DrillDownStep onComplete={jest.fn()} />, { wrapper });

    await waitFor(() => screen.getByText("Communications"));
    fireEvent.click(screen.getByRole("button", { name: /communications/i }));
    await waitFor(() => screen.getByText("Chatbots"));
    fireEvent.click(screen.getByRole("button", { name: /chatbots/i }));
    await waitFor(() => screen.getByText("Acme"));
    fireEvent.click(screen.getByRole("button", { name: /acme/i }));

    await waitFor(() =>
      expect(screen.getByText(/no products found/i)).toBeInTheDocument()
    );
    expect(screen.getByRole("button", { name: /not in catalogue/i })).toBeInTheDocument();
  });

  // ── DrillDownResult shape ─────────────────────────────────────────────────

  test("catalogue product yields isCustom=false with catalogueProductId set", async () => {
    mockFetchByPath({
      "top-categories": [
        { id: "top-1", code: "COMMS", name: "Communications", description: null, parent_id: null },
      ],
      "sub-categories:top-1": [
        { id: "sub-1", code: "COMMS_BOT", name: "Chatbots", description: null, parent_id: "top-1" },
      ],
      vendors: [{ id: "v1", name: "Acme", logo_url: null }],
      products: [{ id: "p1", name: "Acme Bot", vendor_id: "v1", logo_url: null }],
      "products/p1": {
        id: "p1",
        name: "Acme Bot",
        logo_url: null,
        vendor: { id: "v1", name: "Acme", logo_url: null },
        categories: [],
        eu_ai_act_subcategories: [],
      },
    });
    const onComplete = jest.fn<void, [DrillDownResult]>();

    render(<DrillDownStep onComplete={onComplete} />, { wrapper });

    await waitFor(() => screen.getByText("Communications"));
    fireEvent.click(screen.getByRole("button", { name: /communications/i }));
    await waitFor(() => screen.getByText("Chatbots"));
    fireEvent.click(screen.getByRole("button", { name: /chatbots/i }));
    await waitFor(() => screen.getByText("Acme Bot"));
    fireEvent.click(screen.getByRole("button", { name: /Acme Bot/i }));
    await waitFor(() => screen.getByRole("button", { name: /use this product/i }));
    fireEvent.click(screen.getByRole("button", { name: /use this product/i }));

    expect(onComplete).toHaveBeenCalledWith({
      isCustom: false,
      catalogueProductId: "p1",
      catalogueProductName: "Acme Bot",
    });
  });

  test("in-house exit yields isCustom=true with catalogueProductId null", async () => {
    mockFetchByPath({ "top-categories": [] });
    const onComplete = jest.fn<void, [DrillDownResult]>();

    render(<DrillDownStep onComplete={onComplete} />, { wrapper });

    await waitFor(() => screen.getByRole("button", { name: /not in catalogue/i }));
    fireEvent.click(screen.getByRole("button", { name: /not in catalogue/i }));

    expect(onComplete).toHaveBeenCalledWith({
      isCustom: true,
      catalogueProductId: null,
      catalogueProductName: null,
    });
  });
});
