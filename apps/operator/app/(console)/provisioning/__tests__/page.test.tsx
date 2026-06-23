/**
 * @jest-environment jsdom
 */
import { render, screen, waitFor, fireEvent, act } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import ProvisioningPage from "../page";

const ME_WITH_PERM = {
  id: "op-1",
  email: "operator@irontrust.test",
  display_name: "Operator",
  permissions: ["tenant:provision"],
};

const ME_NO_PERM = {
  id: "op-2",
  email: "readonly@irontrust.test",
  display_name: "Read Only",
  permissions: [],
};

const TENANT_LIST = [
  { id: "t-1", name: "Acme Corp", slug: "acme", created_at: "2024-01-01T00:00:00Z" },
];

function renderWithClient() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <ProvisioningPage />
    </QueryClientProvider>
  );
}

let fetchCallIndex = 0;
let fetchResponses: Array<{ ok: boolean; status: number; body: unknown }> = [];

function setupFetch(
  responses: Array<{ ok: boolean; status: number; body: unknown }>
) {
  fetchCallIndex = 0;
  fetchResponses = responses;
  global.fetch = jest.fn().mockImplementation(() => {
    const r = fetchResponses[Math.min(fetchCallIndex++, fetchResponses.length - 1)];
    return Promise.resolve({
      ok: r.ok,
      status: r.status,
      text: async () => JSON.stringify(r.body),
    } as Response);
  });
}

function fillAndSubmit(fields: {
  org_name: string;
  slug: string;
  owner_email: string;
  owner_name: string;
}) {
  fireEvent.change(screen.getByLabelText("Organisation name"), {
    target: { value: fields.org_name },
  });
  fireEvent.change(screen.getByLabelText("Slug"), {
    target: { value: fields.slug },
  });
  fireEvent.change(screen.getByLabelText("Owner email"), {
    target: { value: fields.owner_email },
  });
  fireEvent.change(screen.getByLabelText("Owner name"), {
    target: { value: fields.owner_name },
  });
  fireEvent.click(screen.getByRole("button", { name: /provision tenant/i }));
}

afterEach(() => {
  jest.restoreAllMocks();
});

describe("ProvisioningPage", () => {
  describe("permission-poor operator (B1 regression guard)", () => {
    test("renders empty state; issues no GET /platform/tenants; renders no form", async () => {
      setupFetch([{ ok: true, status: 200, body: ME_NO_PERM }]);
      renderWithClient();

      await waitFor(() =>
        expect(
          screen.getByText(/does not have the provisioning permission/i)
        ).toBeInTheDocument()
      );

      expect(screen.queryByRole("form")).not.toBeInTheDocument();

      const calls = (global.fetch as jest.Mock).mock.calls;
      const tenantsCalls = calls.filter((c: unknown[]) =>
        String(c[0]).includes("/platform/tenants")
      );
      expect(tenantsCalls).toHaveLength(0);
    });
  });

  describe("permitted operator", () => {
    test("renders tenant list and provision form", async () => {
      setupFetch([
        { ok: true, status: 200, body: ME_WITH_PERM },
        { ok: true, status: 200, body: TENANT_LIST },
      ]);
      renderWithClient();

      await waitFor(() =>
        expect(screen.getByRole("form", { name: "Provision new tenant" })).toBeInTheDocument()
      );
      await waitFor(() =>
        expect(screen.getByText("Acme Corp")).toBeInTheDocument()
      );
    });

    test("happy path: provision → 201 → success status shown", async () => {
      setupFetch([
        { ok: true, status: 200, body: ME_WITH_PERM },
        { ok: true, status: 200, body: TENANT_LIST },
        { ok: true, status: 201, body: { tenant_id: "t-new", owner_id: "u-new" } },
        { ok: true, status: 200, body: TENANT_LIST },
      ]);
      renderWithClient();

      await waitFor(() =>
        expect(screen.getByRole("form", { name: "Provision new tenant" })).toBeInTheDocument()
      );

      fillAndSubmit({
        org_name: "Beta Co",
        slug: "beta",
        owner_email: "owner@beta.com",
        owner_name: "Beta Owner",
      });

      await waitFor(() =>
        expect(screen.getByRole("status")).toHaveTextContent(/t-new/)
      );
    });

    test("duplicate slug → 409 → conflict alert on slug field", async () => {
      setupFetch([
        { ok: true, status: 200, body: ME_WITH_PERM },
        { ok: true, status: 200, body: TENANT_LIST },
        {
          ok: false,
          status: 409,
          body: { detail: "tenant slug already exists: 'acme'" },
        },
      ]);
      renderWithClient();

      await waitFor(() =>
        expect(screen.getByRole("form", { name: "Provision new tenant" })).toBeInTheDocument()
      );

      fillAndSubmit({
        org_name: "Acme 2",
        slug: "acme",
        owner_email: "other@acme.com",
        owner_name: "Other Owner",
      });

      await waitFor(() =>
        expect(
          screen.queryAllByRole("alert").some((el) =>
            el.textContent?.includes("Already provisioned")
          )
        ).toBe(true)
      );
    });

    test("duplicate email → 409 → conflict alert on owner_email field", async () => {
      setupFetch([
        { ok: true, status: 200, body: ME_WITH_PERM },
        { ok: true, status: 200, body: TENANT_LIST },
        {
          ok: false,
          status: 409,
          body: { detail: "a user already exists for: 'owner@acme.com'" },
        },
      ]);
      renderWithClient();

      await waitFor(() =>
        expect(screen.getByRole("form", { name: "Provision new tenant" })).toBeInTheDocument()
      );

      fillAndSubmit({
        org_name: "New Corp",
        slug: "new-corp",
        owner_email: "owner@acme.com",
        owner_name: "New Owner",
      });

      await waitFor(() =>
        expect(
          screen.queryAllByRole("alert").some((el) =>
            el.textContent?.includes("user with this email")
          )
        ).toBe(true)
      );
    });

    test("403 → triggers /platform/me refetch", async () => {
      setupFetch([
        { ok: true, status: 200, body: ME_WITH_PERM },
        { ok: true, status: 200, body: [] },
        { ok: false, status: 403, body: { detail: "Forbidden" } },
        { ok: true, status: 200, body: ME_NO_PERM },
      ]);
      renderWithClient();

      await waitFor(() =>
        expect(screen.getByRole("form", { name: "Provision new tenant" })).toBeInTheDocument()
      );

      fillAndSubmit({
        org_name: "Test",
        slug: "test",
        owner_email: "test@test.com",
        owner_name: "Test User",
      });

      await waitFor(() => {
        const calls = (global.fetch as jest.Mock).mock.calls;
        const meCalls = calls.filter((c: unknown[]) =>
          String(c[0]).includes("/platform/me")
        );
        expect(meCalls.length).toBeGreaterThanOrEqual(2);
      });
    });
  });
});
