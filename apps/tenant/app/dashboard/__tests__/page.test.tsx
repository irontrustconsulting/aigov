/**
 * @jest-environment jsdom
 */
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import DashboardPage from "../page";

function renderWithClient() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <DashboardPage />
    </QueryClientProvider>
  );
}

function mockFetchSequence(whoami: unknown, me: unknown) {
  global.fetch = jest.fn((input: RequestInfo | URL) => {
    const url = String(input);
    const body = url.includes("/v1/me") ? me : whoami;
    return Promise.resolve({
      ok: true,
      status: 200,
      text: async () => JSON.stringify(body),
    } as Response);
  }) as jest.Mock;
}

afterEach(() => {
  jest.restoreAllMocks();
});

describe("DashboardPage (W7a/W7b smoke surface)", () => {
  test("renders the caller's identity from GET /v1/whoami (W7a)", async () => {
    mockFetchSequence(
      { sub: "s1", email: "owner@acme.test", name: "Owner", tenant_id: "tenant-1", role: "admin" },
      { membership_id: "m1", tenant_id: "tenant-1", role: "admin", email: "owner@acme.test", name: "Owner", governance_roles: [] }
    );

    renderWithClient();

    await waitFor(() => expect(screen.getByText("owner@acme.test")).toBeInTheDocument());
    expect(screen.getByText("tenant-1")).toBeInTheDocument();
  });

  test("shows the assurance affordance when the caller holds an assurance governance role (W7b)", async () => {
    mockFetchSequence(
      { sub: "s1", email: "reviewer@acme.test", name: "R", tenant_id: "tenant-1", role: "member" },
      {
        membership_id: "m1",
        tenant_id: "tenant-1",
        role: "member",
        email: "reviewer@acme.test",
        name: "R",
        governance_roles: [
          { id: "g1", key: "reviewer", name: "Reviewer", description: null, line_of_defence: 2 },
        ],
      }
    );

    renderWithClient();
    await waitFor(() =>
      expect(screen.getByLabelText("assurance-affordance")).toBeInTheDocument()
    );
    expect(screen.getByLabelText("adoption-affordance")).toBeInTheDocument();
  });

  test("hides the assurance affordance when the caller holds no assurance role, and shows it again on refetch after a role is added", async () => {
    mockFetchSequence(
      { sub: "s1", email: "member@acme.test", name: "M", tenant_id: "tenant-1", role: "member" },
      {
        membership_id: "m1",
        tenant_id: "tenant-1",
        role: "member",
        email: "member@acme.test",
        name: "M",
        governance_roles: [],
      }
    );

    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <DashboardPage />
      </QueryClientProvider>
    );

    await waitFor(() => expect(screen.getByText("member@acme.test")).toBeInTheDocument());
    expect(screen.queryByLabelText("assurance-affordance")).not.toBeInTheDocument();

    // Server-side role grant — re-mock the next fetch and invalidate, as the
    // real app does after any consequential mutation (FE-7).
    mockFetchSequence(
      { sub: "s1", email: "member@acme.test", name: "M", tenant_id: "tenant-1", role: "member" },
      {
        membership_id: "m1",
        tenant_id: "tenant-1",
        role: "member",
        email: "member@acme.test",
        name: "M",
        governance_roles: [
          { id: "g1", key: "authoriser", name: "Authoriser", description: null, line_of_defence: 2 },
        ],
      }
    );
    await client.invalidateQueries({ queryKey: ["me"] });

    await waitFor(() =>
      expect(screen.getByLabelText("assurance-affordance")).toBeInTheDocument()
    );
  });
});
