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
    // No fetch needed — catalogueProductId=null disables the query (enabled: false)
    render(<PrefillStep catalogueProductId={null} onContinue={jest.fn()} />, { wrapper });

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

    render(<PrefillStep catalogueProductId="p1" onContinue={jest.fn()} />, { wrapper });

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

    render(<PrefillStep catalogueProductId="p1" onContinue={jest.fn()} />, { wrapper });

    await waitFor(() => expect(screen.getByText("EU")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "Override" }));
    fireEvent.click(screen.getByRole("button", { name: "Confirm override" }));

    await waitFor(() => expect(screen.getByText("Not applicable to my system")).toBeInTheDocument());

    const fetchMock = global.fetch as jest.Mock;
    expect(fetchMock.mock.calls.every(([, init]) => (init as RequestInit | undefined)?.method !== "POST")).toBe(
      true
    );
  });

  // WI-5 done-checks

  test("{answer,note} fact → Yes/No chip + note, no raw JSON in DOM", async () => {
    mockFetchOk({
      catalogue_product_id: "p1",
      facts: [
        {
          key: "trains_on_customer_data",
          value: { answer: false, note: "Adobe does not use customer documents to train AI models." },
          source_url: null,
          source_label: null,
          last_checked_at: null,
          provenance: "catalogue_curated",
        },
      ],
    });

    const { container } = render(
      <PrefillStep catalogueProductId="p1" onContinue={jest.fn()} />,
      { wrapper }
    );

    await waitFor(() =>
      expect(container.querySelector("[data-bool='false']")).toBeInTheDocument()
    );
    expect(screen.getByText("Adobe does not use customer documents to train AI models.")).toBeInTheDocument();
    expect(container.textContent).not.toMatch(/\{.*"answer".*\}/);
    expect(container.textContent).not.toContain('"answer"');
  });

  test("{list:[…]} fact → pills, no comma-join string in DOM", async () => {
    mockFetchOk({
      catalogue_product_id: "p1",
      facts: [
        {
          key: "certifications",
          value: { list: ["ISO 27001", "SOC 2", "GDPR"] },
          source_url: null,
          source_label: null,
          last_checked_at: null,
          provenance: "catalogue_curated",
        },
      ],
    });

    const { container } = render(
      <PrefillStep catalogueProductId="p1" onContinue={jest.fn()} />,
      { wrapper }
    );

    await waitFor(() => expect(screen.getByText("ISO 27001")).toBeInTheDocument());
    expect(screen.getByText("SOC 2")).toBeInTheDocument();
    expect(screen.getByText("GDPR")).toBeInTheDocument();
    expect(container.textContent).not.toContain("ISO 27001,SOC 2");
  });

  test("each card shows its labelForFactKey label", async () => {
    mockFetchOk({
      catalogue_product_id: "p1",
      facts: [
        {
          key: "dpa_available",
          value: { answer: true },
          source_url: null,
          source_label: null,
          last_checked_at: null,
          provenance: "catalogue_curated",
        },
        {
          key: "eea_entity",
          value: { entity: "EU" },
          source_url: null,
          source_label: null,
          last_checked_at: null,
          provenance: "catalogue_curated",
        },
      ],
    });

    render(<PrefillStep catalogueProductId="p1" onContinue={jest.fn()} />, { wrapper });

    await waitFor(() => expect(screen.getByText("DPA available")).toBeInTheDocument());
    expect(screen.getByText("EEA contracting entity")).toBeInTheDocument();
  });

  test("overriding a fact swaps value slot to override label; badge stays catalogue_curated (R9)", async () => {
    mockFetchOk({
      catalogue_product_id: "p1",
      facts: [
        {
          key: "trains_on_customer_data",
          value: { answer: false, note: "Not used." },
          source_url: null,
          source_label: null,
          last_checked_at: null,
          provenance: "catalogue_curated",
        },
      ],
    });

    const { container } = render(
      <PrefillStep catalogueProductId="p1" onContinue={jest.fn()} />,
      { wrapper }
    );

    await waitFor(() =>
      expect(container.querySelector("[data-bool='false']")).toBeInTheDocument()
    );

    // Override the fact
    fireEvent.click(screen.getByRole("button", { name: "Override" }));
    fireEvent.click(screen.getByRole("button", { name: "Confirm override" }));

    await waitFor(() =>
      expect(screen.getByText("Not applicable to my system")).toBeInTheDocument()
    );
    // Typed node (bool chip) gone; override label shown
    expect(container.querySelector("[data-bool]")).not.toBeInTheDocument();
    // Badge still shows catalogue_curated (R9)
    expect(screen.getByText("Catalogue")).toBeInTheDocument();
  });

  test("Continue emits the correct confirmed/amended split (INV-83)", async () => {
    const onContinue = jest.fn();
    mockFetchOk({
      catalogue_product_id: "p1",
      facts: [
        {
          key: "certifications",
          value: { list: ["ISO 27001"] },
          source_url: null,
          source_label: null,
          last_checked_at: null,
          provenance: "catalogue_curated",
        },
        {
          key: "dpa_available",
          value: { answer: true },
          source_url: null,
          source_label: null,
          last_checked_at: null,
          provenance: "catalogue_curated",
        },
      ],
    });

    render(<PrefillStep catalogueProductId="p1" onContinue={onContinue} />, { wrapper });

    await waitFor(() => expect(screen.getByText("ISO 27001")).toBeInTheDocument());

    // Override only dpa_available
    fireEvent.click(screen.getAllByRole("button", { name: "Override" })[1]!);
    fireEvent.click(screen.getByRole("button", { name: "Confirm override" }));

    fireEvent.click(screen.getByRole("button", { name: /continue/i }));

    expect(onContinue).toHaveBeenCalledWith(["certifications"], ["dpa_available"]);
  });

  test("confirm caption present with facts, absent in error return", async () => {
    // With facts — caption present
    mockFetchOk({
      catalogue_product_id: "p1",
      facts: [
        {
          key: "certifications",
          value: { list: ["ISO 27001"] },
          source_url: null,
          source_label: null,
          last_checked_at: null,
          provenance: "catalogue_curated",
        },
      ],
    });

    const { unmount } = render(
      <PrefillStep catalogueProductId="p1" onContinue={jest.fn()} />,
      { wrapper }
    );

    await waitFor(() => expect(screen.getByText("ISO 27001")).toBeInTheDocument());
    expect(
      screen.getByText(/facts you don't amend are recorded as confirmed/i)
    ).toBeInTheDocument();
    unmount();

    // Error path — caption absent
    global.fetch = jest.fn().mockResolvedValue({
      ok: false,
      status: 500,
      text: async () => "error",
    } as Response) as jest.Mock;

    render(<PrefillStep catalogueProductId="p1" onContinue={jest.fn()} />, { wrapper });

    await waitFor(() => expect(screen.getByRole("button", { name: /continue/i })).toBeInTheDocument());
    expect(
      screen.queryByText(/facts you don't amend are recorded as confirmed/i)
    ).not.toBeInTheDocument();
  });
});
