/**
 * @jest-environment jsdom
 *
 * DrillDownStep accordion (D-56) done-checks:
 * - Full funnel including single-vendor auto-skip
 * - Single-open collapse among branch siblings
 * - All four INV-70 states
 * - In-house exit → {isCustom:true, catalogueProductId:null}
 * - Catalogue product → {isCustom:false, catalogueProductId:<id>}
 * - DrillDownResult shape unchanged
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
 * Mock that routes by URL path + query. Keys:
 *   "top-categories"             product-categories (no parent_id)
 *   "sub-categories:{parentId}"  product-categories?parent_id=xxx
 *   "vendors:{catId}"            {catId}/vendors
 *   "products:{catId}"           {catId}/products (with or without vendor_id filter)
 *   "products/{id}"              reference/products/{id}  (detail)
 */
function mockFetchByPath(map: Record<string, unknown>) {
  global.fetch = jest.fn((input: RequestInfo | URL) => {
    const full = String(input);
    const [pathname, queryStr = ""] = full.split("?");
    const params = new URLSearchParams(queryStr);
    const segments = pathname.split("/").filter(Boolean);
    const last = segments[segments.length - 1];
    const v1At = segments.indexOf("v1");
    const resource = v1At >= 0 ? segments[v1At + 2] : undefined;

    let key: string | undefined;
    if (last === "vendors") {
      const catId = segments[segments.length - 2];
      key = `vendors:${catId}`;
    } else if (last === "products" && resource !== "products") {
      // category-level products: {catId}/products[?vendor_id=...]
      const catId = segments[segments.length - 2];
      key = `products:${catId}`;
    } else if (resource === "products") {
      // product detail: reference/products/{id}
      key = `products/${last}`;
    } else if (resource === "product-categories") {
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

describe("DrillDownStep — accordion (D-56)", () => {
  // ── INV-70: empty taxonomy ────────────────────────────────────────────────

  test("empty taxonomy shows EmptyState with in-house exit", async () => {
    mockFetchByPath({ "top-categories": [] });
    render(<DrillDownStep onComplete={jest.fn()} />, { wrapper });

    await waitFor(() =>
      expect(screen.getByText(/no categories available/i)).toBeInTheDocument()
    );
    expect(screen.getByRole("button", { name: /not in catalogue/i })).toBeInTheDocument();
  });

  // ── In-house exit → isCustom=true ────────────────────────────────────────

  test("in-house exit yields isCustom=true with null product", async () => {
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

  test("PageHeader Go back affordance calls exitCustom (in-house exit)", async () => {
    mockFetchByPath({
      "top-categories": [
        { id: "top-1", code: "CAT", name: "AI Tools", description: null, parent_id: null },
      ],
    });
    const onComplete = jest.fn<void, [DrillDownResult]>();

    render(<DrillDownStep onComplete={onComplete} />, { wrapper });

    await waitFor(() => screen.getByText("AI Tools"));
    fireEvent.click(screen.getByRole("button", { name: "Go back" }));

    expect(onComplete).toHaveBeenCalledWith({
      isCustom: true,
      catalogueProductId: null,
      catalogueProductName: null,
    });
  });

  // ── Full funnel — single vendor (auto-skip) ───────────────────────────────

  test("single-vendor auto-skip: category → sub-category → product → confirm", async () => {
    mockFetchByPath({
      "top-categories": [
        { id: "top-1", code: "COMMS", name: "Communications", description: null, parent_id: null },
      ],
      "sub-categories:top-1": [
        { id: "sub-1", code: "COMMS_BOT", name: "Chatbots", description: null, parent_id: "top-1" },
      ],
      "vendors:sub-1": [{ id: "v1", name: "Acme", logo_url: null }],
      "products:sub-1": [{ id: "p1", name: "Acme Bot", vendor_id: "v1", logo_url: null }],
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

    // Expand category
    await waitFor(() => screen.getByText("Communications"));
    fireEvent.click(screen.getByRole("button", { name: /communications/i }));

    // Sub-categories appear inline
    await waitFor(() => screen.getByText("Chatbots"));
    fireEvent.click(screen.getByRole("button", { name: /chatbots/i }));

    // Auto-skip fires → products appear directly (no vendor rung)
    // findByRole retries until the button is stably accessible (avoids the
    // transient loading state that fires between auto-skip and second fetch)
    const botButton = await screen.findByRole("button", { name: /Acme Bot/i });
    expect(screen.queryByText("Acme")).toBeNull(); // vendor row not shown

    fireEvent.click(botButton);

    // Confirm stage
    await waitFor(() => screen.getByRole("button", { name: /use this product/i }));
    fireEvent.click(screen.getByRole("button", { name: /use this product/i }));

    expect(onComplete).toHaveBeenCalledWith({
      isCustom: false,
      catalogueProductId: "p1",
      catalogueProductName: "Acme Bot",
    });
  });

  // ── Full funnel — multi-vendor ────────────────────────────────────────────

  test("multi-vendor: vendor rung shown, product filtered to chosen vendor", async () => {
    mockFetchByPath({
      "top-categories": [
        { id: "top-1", code: "COMMS", name: "Communications", description: null, parent_id: null },
      ],
      "sub-categories:top-1": [
        { id: "sub-1", code: "COMMS_BOT", name: "Chatbots", description: null, parent_id: "top-1" },
      ],
      "vendors:sub-1": [
        { id: "v1", name: "Acme", logo_url: null },
        { id: "v2", name: "Beta AI", logo_url: null },
      ],
      "products:sub-1": [{ id: "p2", name: "Beta Bot", vendor_id: "v2", logo_url: null }],
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

    // Products for Beta AI appear inline
    await waitFor(() => screen.getByText("Beta Bot"));
    fireEvent.click(screen.getByRole("button", { name: /beta bot/i }));

    await waitFor(() => screen.getByRole("button", { name: /use this product/i }));
    fireEvent.click(screen.getByRole("button", { name: /use this product/i }));

    expect(onComplete).toHaveBeenCalledWith({
      isCustom: false,
      catalogueProductId: "p2",
      catalogueProductName: "Beta Bot",
    });
  });

  // ── Single-open: expanding one category collapses siblings ────────────────

  test("single-open: expanding a second category collapses the first", async () => {
    mockFetchByPath({
      "top-categories": [
        { id: "top-1", code: "CAT1", name: "Category A", description: null, parent_id: null },
        { id: "top-2", code: "CAT2", name: "Category B", description: null, parent_id: null },
      ],
      "sub-categories:top-1": [
        { id: "sub-a", code: "SUB_A", name: "Sub A", description: null, parent_id: "top-1" },
      ],
      "sub-categories:top-2": [
        { id: "sub-b", code: "SUB_B", name: "Sub B", description: null, parent_id: "top-2" },
      ],
      "vendors:sub-1": [],
    });

    render(<DrillDownStep onComplete={jest.fn()} />, { wrapper });

    // Expand Category A
    await waitFor(() => screen.getByText("Category A"));
    fireEvent.click(screen.getByRole("button", { name: /category a/i }));
    await waitFor(() => screen.getByText("Sub A"));

    // Expand Category B — should collapse Category A
    fireEvent.click(screen.getByRole("button", { name: /category b/i }));
    await waitFor(() => screen.getByText("Sub B"));
    expect(screen.queryByText("Sub A")).toBeNull();
  });

  // ── Accordion collapse (back) ─────────────────────────────────────────────

  test("re-clicking an expanded category collapses it (collapse is back)", async () => {
    mockFetchByPath({
      "top-categories": [
        { id: "top-1", code: "CAT", name: "AI Tools", description: null, parent_id: null },
      ],
      "sub-categories:top-1": [
        { id: "sub-1", code: "SUB", name: "Assistants", description: null, parent_id: "top-1" },
      ],
      "vendors:sub-1": [],
    });

    render(<DrillDownStep onComplete={jest.fn()} />, { wrapper });

    await waitFor(() => screen.getByText("AI Tools"));
    fireEvent.click(screen.getByRole("button", { name: /ai tools/i }));
    await waitFor(() => screen.getByText("Assistants"));

    // Re-click to collapse
    fireEvent.click(screen.getByRole("button", { name: /ai tools/i }));
    await waitFor(() => expect(screen.queryByText("Assistants")).toBeNull());
  });

  // ── Back from confirm stage ───────────────────────────────────────────────

  test("Go back from confirm stage returns to product list", async () => {
    mockFetchByPath({
      "top-categories": [
        { id: "top-1", code: "COMMS", name: "Communications", description: null, parent_id: null },
      ],
      "sub-categories:top-1": [
        { id: "sub-1", code: "COMMS_BOT", name: "Chatbots", description: null, parent_id: "top-1" },
      ],
      "vendors:sub-1": [{ id: "v1", name: "Acme", logo_url: null }],
      "products:sub-1": [{ id: "p1", name: "Acme Bot", vendor_id: "v1", logo_url: null }],
      "products/p1": {
        id: "p1",
        name: "Acme Bot",
        logo_url: null,
        vendor: { id: "v1", name: "Acme", logo_url: null },
        categories: [],
        eu_ai_act_subcategories: [],
      },
    });

    render(<DrillDownStep onComplete={jest.fn()} />, { wrapper });

    await waitFor(() => screen.getByText("Communications"));
    fireEvent.click(screen.getByRole("button", { name: /communications/i }));
    await waitFor(() => screen.getByText("Chatbots"));
    fireEvent.click(screen.getByRole("button", { name: /chatbots/i }));
    fireEvent.click(await screen.findByRole("button", { name: /Acme Bot/i }));

    await waitFor(() => screen.getByRole("button", { name: /use this product/i }));
    fireEvent.click(screen.getByRole("button", { name: "Go back" }));

    // Returns to the accordion (product list visible again)
    await waitFor(() => expect(screen.getByText("Acme Bot")).toBeInTheDocument());
    expect(screen.queryByRole("button", { name: /use this product/i })).toBeNull();
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
      "vendors:sub-1": [],
    });

    render(<DrillDownStep onComplete={jest.fn()} />, { wrapper });

    await waitFor(() => screen.getByText("Communications"));
    fireEvent.click(screen.getByRole("button", { name: /communications/i }));
    await waitFor(() => screen.getByText("Chatbots"));
    fireEvent.click(screen.getByRole("button", { name: /chatbots/i }));

    await waitFor(() =>
      expect(screen.getByText(/no vendors available/i)).toBeInTheDocument()
    );
    const exitButtons = screen.getAllByRole("button", { name: /not in catalogue/i });
    expect(exitButtons.length).toBeGreaterThan(0);
  });

  test("empty product list shows EmptyState with in-house exit", async () => {
    mockFetchByPath({
      "top-categories": [
        { id: "top-1", code: "COMMS", name: "Communications", description: null, parent_id: null },
      ],
      "sub-categories:top-1": [
        { id: "sub-1", code: "COMMS_BOT", name: "Chatbots", description: null, parent_id: "top-1" },
      ],
      "vendors:sub-1": [
        { id: "v1", name: "Acme", logo_url: null },
        { id: "v2", name: "Beta AI", logo_url: null },
      ],
      "products:sub-1": [],
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
    const exitButtons = screen.getAllByRole("button", { name: /not in catalogue/i });
    expect(exitButtons.length).toBeGreaterThan(0);
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
      "vendors:sub-1": [],
    });
    const onComplete = jest.fn<void, [DrillDownResult]>();

    render(<DrillDownStep onComplete={onComplete} />, { wrapper });

    await waitFor(() => screen.getByText("Communications"));
    fireEvent.click(screen.getByRole("button", { name: /communications/i }));
    await waitFor(() => screen.getByText("Chatbots"));

    // The bottom "Not in catalogue" button
    const buttons = screen.getAllByRole("button", { name: /not in catalogue/i });
    fireEvent.click(buttons[buttons.length - 1]);

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
      "vendors:sub-1": [
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

    const buttons = screen.getAllByRole("button", { name: /not in catalogue/i });
    fireEvent.click(buttons[buttons.length - 1]);

    expect(onComplete).toHaveBeenCalledWith({
      isCustom: true,
      catalogueProductId: null,
      catalogueProductName: null,
    });
  });

  // ── DrillDownResult shape unchanged ──────────────────────────────────────

  test("catalogue product: isCustom=false, catalogueProductId set", async () => {
    mockFetchByPath({
      "top-categories": [
        { id: "top-1", code: "COMMS", name: "Communications", description: null, parent_id: null },
      ],
      "sub-categories:top-1": [
        { id: "sub-1", code: "COMMS_BOT", name: "Chatbots", description: null, parent_id: "top-1" },
      ],
      "vendors:sub-1": [{ id: "v1", name: "Acme", logo_url: null }],
      "products:sub-1": [{ id: "p1", name: "Acme Bot", vendor_id: "v1", logo_url: null }],
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
    fireEvent.click(await screen.findByRole("button", { name: /Acme Bot/i }));
    await waitFor(() => screen.getByRole("button", { name: /use this product/i }));
    fireEvent.click(screen.getByRole("button", { name: /use this product/i }));

    expect(onComplete).toHaveBeenCalledWith({
      isCustom: false,
      catalogueProductId: "p1",
      catalogueProductName: "Acme Bot",
    });
  });
});
