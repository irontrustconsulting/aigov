/**
 * @jest-environment jsdom
 */
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { PrefillStep } from "../prefill-step";

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

function mockFetchOk(body: unknown) {
  global.fetch = jest.fn().mockResolvedValue({
    ok: true,
    status: 200,
    text: async () => JSON.stringify(body),
  } as Response) as jest.Mock;
}

afterEach(() => {
  jest.restoreAllMocks();
});

describe("PrefillStep", () => {
  test("an empty facts list (custom system) renders no panel and no error", async () => {
    mockFetchOk({ catalogue_product_id: null, facts: [] });

    render(<PrefillStep systemId="sys-1" onContinue={jest.fn()} />, { wrapper });

    await waitFor(() => expect(screen.getByRole("button", { name: /continue/i })).toBeInTheDocument());
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(screen.queryByRole("list")).not.toBeInTheDocument();
  });

  test("a catalogue system renders facts with provenance badges and issues no mutation", async () => {
    mockFetchOk({
      catalogue_product_id: "p1",
      facts: [
        {
          key: "hosting_region",
          value: { region: "EU" },
          source_url: "https://vendor.example/docs",
          source_label: "Vendor documentation",
          last_checked_at: "2026-01-01T00:00:00Z",
          provenance: "catalogue_curated",
        },
      ],
    });

    render(<PrefillStep systemId="sys-1" onContinue={jest.fn()} />, { wrapper });

    await waitFor(() => expect(screen.getByText("EU")).toBeInTheDocument());
    expect(screen.getByText("Catalogue")).toBeInTheDocument(); // ProvenanceBadge label
    expect(screen.getByText(/vendor documentation/i)).toBeInTheDocument();

    const fetchMock = global.fetch as jest.Mock;
    expect(fetchMock.mock.calls.every(([, init]) => (init as RequestInit | undefined)?.method !== "POST")).toBe(
      true
    );
  });

  test("an override updates the displayed value only — still no mutation issued", async () => {
    mockFetchOk({
      catalogue_product_id: "p1",
      facts: [
        {
          key: "hosting_region",
          value: { region: "EU" },
          source_url: null,
          source_label: null,
          last_checked_at: null,
          provenance: "catalogue_curated",
        },
      ],
    });

    render(<PrefillStep systemId="sys-1" onContinue={jest.fn()} />, { wrapper });

    await waitFor(() => expect(screen.getByText("EU")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "Override" }));
    fireEvent.click(screen.getByRole("button", { name: "Confirm override" }));

    await waitFor(() => expect(screen.getByText("Not applicable to my system")).toBeInTheDocument());

    const fetchMock = global.fetch as jest.Mock;
    expect(fetchMock.mock.calls.every(([, init]) => (init as RequestInit | undefined)?.method !== "POST")).toBe(
      true
    );
  });
});
