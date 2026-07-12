/**
 * @jest-environment jsdom
 *
 * UI-F10-CLEARANCE WI-3 done-checks.
 */
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import type { ClearanceQueueRead, MeRead, VendorClearanceEntry } from "@irontrust/api-client";
import { ClearancesClient } from "../clearances-client";

function makeMeRead(governanceRoleKeys: string[]): MeRead {
  return {
    membership_id: "m-1",
    tenant_id: "t-1",
    role: "member",
    email: "user@acme.test",
    name: "Test User",
    tenant_name: "Acme Corp",
    governance_roles: governanceRoleKeys.map((key) => ({
      id: `role-${key}`,
      key,
      name: key,
      description: null,
      line_of_defence: 1,
    })),
  };
}

function makeVendorEntry(overrides: Partial<VendorClearanceEntry> = {}): VendorClearanceEntry {
  return {
    catalogue_vendor_id: "v-1",
    vendor_name: "Acme Vendor",
    status: "not_started",
    valid_until: null,
    decided_by_name: null,
    decided_at: null,
    note: null,
    awaiting_use_case_count: 1,
    affected_use_case_count: 2,
    affected_system_count: 2,
    products: [],
    ...overrides,
  };
}

const QUEUE_WITH_PRODUCT: ClearanceQueueRead = {
  vendors: [
    makeVendorEntry({
      status: "not_started",
      products: [
        {
          catalogue_product_id: "p-1",
          product_name: "Acme Widget",
          status: "not_started",
          valid_until: null,
          decided_by_name: null,
          decided_at: null,
          note: null,
          vendor_cleared: false,
          awaiting_use_case_count: 0,
          affected_use_case_count: 1,
          affected_system_count: 1,
        },
      ],
    }),
  ],
};

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

function mockFetch({
  meData,
  queue = QUEUE_WITH_PRODUCT,
  putStatus = 200,
}: {
  meData: MeRead;
  queue?: ClearanceQueueRead;
  putStatus?: number;
}) {
  global.fetch = jest.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    const method = (init?.method ?? "GET").toUpperCase();

    if (url.includes("/v1/me")) {
      return Promise.resolve({ ok: true, status: 200, text: async () => JSON.stringify(meData) } as Response);
    }
    if (url.includes("/vendors/") && method === "PUT") {
      return Promise.resolve({
        ok: putStatus < 400,
        status: putStatus,
        text: async () =>
          JSON.stringify({
            id: "va-1",
            catalogue_vendor_id: "v-1",
            status: "approved",
            valid_until: null,
            decided_by_user_id: "u-1",
            decided_at: "2026-07-12T00:00:00Z",
            note: null,
          }),
      } as Response);
    }
    if (url.includes("/v1/clearance-queue")) {
      return Promise.resolve({ ok: true, status: 200, text: async () => JSON.stringify(queue) } as Response);
    }
    return Promise.resolve({ ok: true, status: 200, text: async () => JSON.stringify({}) } as Response);
  }) as jest.Mock;
}

function fetchedUrls(): string[] {
  return (global.fetch as jest.Mock).mock.calls.map(([url]: [RequestInfo | URL]) => String(url));
}

afterEach(() => jest.restoreAllMocks());

describe("Role branch (DF-CLR-17)", () => {
  test("admin (zero governance roles): EmptyState rendered, no GET /clearance-queue call", async () => {
    mockFetch({ meData: makeMeRead([]) });

    render(<ClearancesClient />, { wrapper });

    await waitFor(() =>
      expect(screen.getByText(/visible to callers holding a governance role/i)).toBeInTheDocument()
    );

    expect(fetchedUrls().filter((u) => u.includes("/clearance-queue"))).toHaveLength(0);
  });

  test("auditor: queue renders read-only, no set-clearance control", async () => {
    mockFetch({ meData: makeMeRead(["auditor"]) });

    render(<ClearancesClient />, { wrapper });

    await waitFor(() => expect(screen.getByText("Acme Vendor")).toBeInTheDocument());

    expect(screen.queryByRole("button", { name: /set clearance/i })).not.toBeInTheDocument();
  });

  test("reviewer: queue renders read-only, no set-clearance control", async () => {
    mockFetch({ meData: makeMeRead(["reviewer"]) });

    render(<ClearancesClient />, { wrapper });

    await waitFor(() => expect(screen.getByText("Acme Vendor")).toBeInTheDocument());

    expect(screen.queryByRole("button", { name: /set clearance/i })).not.toBeInTheDocument();
  });

  test("system_owner: queue renders read-only, no set-clearance control", async () => {
    mockFetch({ meData: makeMeRead(["system_owner"]) });

    render(<ClearancesClient />, { wrapper });

    await waitFor(() => expect(screen.getByText("Acme Vendor")).toBeInTheDocument());

    expect(screen.queryByRole("button", { name: /set clearance/i })).not.toBeInTheDocument();
  });

  test("authoriser: set-clearance control present", async () => {
    mockFetch({ meData: makeMeRead(["authoriser"]) });

    render(<ClearancesClient />, { wrapper });

    await waitFor(() =>
      expect(screen.getAllByRole("button", { name: /set clearance/i }).length).toBeGreaterThan(0)
    );
  });
});

describe("Product gating (INV-88) and status rendering", () => {
  test("product action disabled-with-reason when parent vendor is not approved", async () => {
    mockFetch({ meData: makeMeRead(["authoriser"]) });

    render(<ClearancesClient />, { wrapper });

    await waitFor(() => expect(screen.getByText("Acme Widget")).toBeInTheDocument());

    const productRow = screen.getByText("Acme Widget").closest("tr")!;
    const productButton = within(productRow).getByRole("button", { name: /set clearance/i });
    expect(productButton).toBeDisabled();
    expect(productButton).toHaveAttribute("title", "Clear the vendor first");
  });

  test("product action enabled when parent vendor is approved", async () => {
    const queue: ClearanceQueueRead = {
      vendors: [
        makeVendorEntry({
          status: "approved",
          products: [
            {
              catalogue_product_id: "p-1",
              product_name: "Acme Widget",
              status: "not_started",
              valid_until: null,
              decided_by_name: null,
              decided_at: null,
              note: null,
              vendor_cleared: true,
              awaiting_use_case_count: 1,
              affected_use_case_count: 1,
              affected_system_count: 1,
            },
          ],
        }),
      ],
    };
    mockFetch({ meData: makeMeRead(["authoriser"]), queue });

    render(<ClearancesClient />, { wrapper });

    await waitFor(() => expect(screen.getByText("Acme Widget")).toBeInTheDocument());

    const productRow = screen.getByText("Acme Widget").closest("tr")!;
    const productButton = within(productRow).getByRole("button", { name: /set clearance/i });
    expect(productButton).not.toBeDisabled();
  });

  test("status chip renders the authored approval_status label", async () => {
    mockFetch({ meData: makeMeRead(["auditor"]) });

    render(<ClearancesClient />, { wrapper });

    await waitFor(() => expect(screen.getAllByText("Not started").length).toBeGreaterThan(0));
  });
});

describe("Set-clearance form (authoriser)", () => {
  async function openVendorForm() {
    mockFetch({ meData: makeMeRead(["authoriser"]) });
    render(<ClearancesClient />, { wrapper });
    await waitFor(() => expect(screen.getByText("Acme Vendor")).toBeInTheDocument());
    const [firstSetButton] = screen.getAllByRole("button", { name: /set clearance/i });
    fireEvent.click(firstSetButton!);
    await screen.findByRole("dialog");
  }

  test("status select offers exactly {Under review, Approved, Rejected}", async () => {
    await openVendorForm();

    const select = screen.getByLabelText(/^status$/i) as HTMLSelectElement;
    const optionLabels = Array.from(select.options).map((o) => o.text);
    expect(optionLabels).toEqual(
      expect.arrayContaining(["Under review", "Approved", "Rejected"])
    );
    expect(optionLabels).not.toEqual(expect.arrayContaining(["Not started", "Expired"]));
  });

  test("selecting Approved prefills valid_until to today plus one year", async () => {
    await openVendorForm();

    const select = screen.getByLabelText(/^status$/i) as HTMLSelectElement;
    fireEvent.change(select, { target: { value: "approved" } });

    const dateInput = screen.getByLabelText(/valid until/i) as HTMLInputElement;
    const expected = new Date();
    expected.setFullYear(expected.getFullYear() + 1);
    expect(dateInput.value).toBe(expected.toISOString().slice(0, 10));
  });

  test("a past valid_until date is rejected client-side", async () => {
    await openVendorForm();

    const select = screen.getByLabelText(/^status$/i);
    fireEvent.change(select, { target: { value: "approved" } });

    const dateInput = screen.getByLabelText(/valid until/i);
    fireEvent.change(dateInput, { target: { value: "2020-01-01" } });

    fireEvent.click(screen.getByRole("button", { name: /^review$/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/future/i);
    // Still on the form stage — no confirm-step text rendered.
    expect(screen.queryByText(/will re-evaluate/i)).not.toBeInTheDocument();
  });

  test("confirm step displays affected_use_case_count", async () => {
    await openVendorForm();

    fireEvent.change(screen.getByLabelText(/^status$/i), { target: { value: "under_review" } });
    fireEvent.click(screen.getByRole("button", { name: /^review$/i }));

    const dialog = await screen.findByRole("dialog");
    await waitFor(() =>
      expect(dialog.textContent).toMatch(/will re-evaluate 2 use cases across 2 systems/i)
    );
  });

  test("successful submit invalidates clearance-queue and portfolio, closes the dialog", async () => {
    await openVendorForm();

    fireEvent.change(screen.getByLabelText(/^status$/i), { target: { value: "under_review" } });
    fireEvent.click(screen.getByRole("button", { name: /^review$/i }));
    const dialog = await screen.findByRole("dialog");
    await waitFor(() => expect(dialog.textContent).toMatch(/will re-evaluate/i));

    fireEvent.click(screen.getByRole("button", { name: /^confirm$/i }));

    await waitFor(() => {
      const putCalls = (global.fetch as jest.Mock).mock.calls.filter(
        ([u, i]: [RequestInfo | URL, RequestInit]) =>
          String(u).includes("/vendors/") && (i?.method ?? "GET").toUpperCase() === "PUT"
      );
      expect(putCalls).toHaveLength(1);
    });

    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());

    // Cache invalidation refetches the live-state clearance-queue query.
    await waitFor(() => {
      const queueCalls = fetchedUrls().filter((u) => u.includes("/v1/clearance-queue"));
      expect(queueCalls.length).toBeGreaterThan(1);
    });
  });
});
