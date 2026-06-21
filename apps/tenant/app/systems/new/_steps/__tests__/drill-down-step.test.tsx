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

function mockFetchByPath(map: Record<string, unknown>) {
  global.fetch = jest.fn((input: RequestInfo | URL) => {
    const url = String(input);
    const pathname = url.split("?")[0] ?? "";
    const segments = pathname.split("/").filter(Boolean);
    const last = segments[segments.length - 1];
    const v1At = segments.indexOf("v1");
    const resource = segments[v1At + 2]; // segments: [..., "v1", "reference", <resource>, ...]

    let key: string | undefined;
    if (last === "vendors") key = "vendors";
    else if (last === "products") key = "products";
    else if (resource === "products") key = `products/${last}`; // product detail
    else if (resource === "product-categories") key = "product-categories";

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
  test("renders cleanly with an empty taxonomy and offers the custom exit", async () => {
    mockFetchByPath({ "product-categories": [] });
    const onComplete = jest.fn();

    render(<DrillDownStep onComplete={onComplete} />, { wrapper });

    await waitFor(() =>
      expect(screen.getByText(/no categories here/i)).toBeInTheDocument()
    );
    expect(screen.getByRole("button", { name: /not in catalogue/i })).toBeInTheDocument();
  });

  test("the custom branch carries is_custom=true and no product forward", async () => {
    mockFetchByPath({ "product-categories": [] });
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

  test("drilling to a product and confirming carries the product forward", async () => {
    mockFetchByPath({
      "product-categories": [{ id: "cat-1", code: "c1", name: "Chatbots", description: null, parent_id: null }],
      vendors: [{ id: "v1", name: "Acme", logo_url: null }],
      products: [{ id: "p1", name: "Acme Bot", vendor_id: "v1", logo_url: null }],
      "products/p1": {
        id: "p1",
        name: "Acme Bot",
        vendor: { id: "v1", name: "Acme" },
        categories: [],
        eu_ai_act_subcategories: [],
      },
    });
    const onComplete = jest.fn<void, [DrillDownResult]>();

    render(<DrillDownStep onComplete={onComplete} />, { wrapper });

    await waitFor(() => screen.getByText("Chatbots"));
    fireEvent.click(screen.getByRole("button", { name: /browse vendors\/products/i }));

    await waitFor(() => screen.getByText("Acme Bot"));
    fireEvent.click(screen.getByRole("button", { name: "Acme Bot" }));

    await waitFor(() => screen.getByRole("button", { name: /use this product/i }));
    fireEvent.click(screen.getByRole("button", { name: /use this product/i }));

    expect(onComplete).toHaveBeenCalledWith({
      isCustom: false,
      catalogueProductId: "p1",
      catalogueProductName: "Acme Bot",
    });
  });
});
