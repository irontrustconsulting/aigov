/**
 * @jest-environment jsdom
 */
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import OperatorsPage from "../page";

const ME_WITH_PERM = {
  id: "op-admin",
  email: "admin@irontrust.test",
  display_name: "Platform Admin",
  permissions: ["tenant:provision", "operator:create"],
};

const ME_NO_PERM = {
  id: "op-prov",
  email: "prov@irontrust.test",
  display_name: "Provisioner",
  permissions: ["tenant:provision"],
};

const OPERATOR_LIST = [
  {
    id: "op-1",
    email: "admin@irontrust.test",
    display_name: "Platform Admin",
    status: "active",
    roles: ["platform_admin"],
  },
];

const ROLES_LIST = [
  { key: "platform_admin", description: "Full platform administration" },
  { key: "provisioner", description: "Can provision new tenants" },
];

function renderWithClient() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <OperatorsPage />
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

afterEach(() => {
  jest.restoreAllMocks();
});

describe("OperatorsPage", () => {
  describe("provisioner-only operator (no operator:create)", () => {
    test("renders nothing; issues zero calls to gated endpoints", async () => {
      setupFetch([{ ok: true, status: 200, body: ME_NO_PERM }]);
      renderWithClient();

      await waitFor(() => {
        const calls = (global.fetch as jest.Mock).mock.calls;
        const meCalls = calls.filter((c: unknown[]) =>
          String(c[0]).includes("/platform/me")
        );
        expect(meCalls.length).toBeGreaterThanOrEqual(1);
      });

      expect(screen.queryByRole("table")).not.toBeInTheDocument();
      expect(screen.queryByRole("form")).not.toBeInTheDocument();

      const calls = (global.fetch as jest.Mock).mock.calls;
      const operatorsCalls = calls.filter((c: unknown[]) =>
        String(c[0]).includes("/platform/operators")
      );
      const rolesCalls = calls.filter((c: unknown[]) =>
        String(c[0]).includes("/platform/roles")
      );
      expect(operatorsCalls).toHaveLength(0);
      expect(rolesCalls).toHaveLength(0);
    });
  });

  describe("platform_admin operator (has operator:create)", () => {
    test("renders operator list and create form", async () => {
      setupFetch([
        { ok: true, status: 200, body: ME_WITH_PERM },
        { ok: true, status: 200, body: OPERATOR_LIST },
        { ok: true, status: 200, body: ROLES_LIST },
      ]);
      renderWithClient();

      await waitFor(() =>
        expect(screen.getByRole("form", { name: "Create new operator" })).toBeInTheDocument()
      );
      await waitFor(() =>
        expect(screen.getByText("admin@irontrust.test")).toBeInTheDocument()
      );
      expect(screen.getAllByText("platform_admin").length).toBeGreaterThan(0);
    });

    test("happy path: create → 201 → invite-sent status shown; operators refetched", async () => {
      const newOp = {
        id: "op-2",
        email: "new@irontrust.test",
        display_name: "New Op",
        status: "active",
        roles: ["provisioner"],
      };
      setupFetch([
        { ok: true, status: 200, body: ME_WITH_PERM },
        { ok: true, status: 200, body: OPERATOR_LIST },
        { ok: true, status: 200, body: ROLES_LIST },
        { ok: true, status: 201, body: { operator_id: "op-2", cognito_sub: "cog-sub-2" } },
        { ok: true, status: 200, body: [...OPERATOR_LIST, newOp] },
      ]);
      renderWithClient();

      await waitFor(() =>
        expect(screen.getByRole("form", { name: "Create new operator" })).toBeInTheDocument()
      );

      fireEvent.change(screen.getByLabelText("Email"), {
        target: { value: "new@irontrust.test" },
      });
      fireEvent.change(screen.getByLabelText("Display name"), {
        target: { value: "New Op" },
      });
      fireEvent.click(screen.getByRole("button", { name: /create operator/i }));

      await waitFor(() =>
        expect(screen.getByRole("status")).toHaveTextContent(/invite sent/i)
      );
      await waitFor(() =>
        expect(screen.getByText("new@irontrust.test")).toBeInTheDocument()
      );
    });

    test("duplicate email → 409 → alert on email field", async () => {
      setupFetch([
        { ok: true, status: 200, body: ME_WITH_PERM },
        { ok: true, status: 200, body: OPERATOR_LIST },
        { ok: true, status: 200, body: ROLES_LIST },
        { ok: false, status: 409, body: { detail: "operator already exists: 'dup@irontrust.test'" } },
      ]);
      renderWithClient();

      await waitFor(() =>
        expect(screen.getByRole("form", { name: "Create new operator" })).toBeInTheDocument()
      );

      fireEvent.change(screen.getByLabelText("Email"), {
        target: { value: "dup@irontrust.test" },
      });
      fireEvent.change(screen.getByLabelText("Display name"), {
        target: { value: "Dup" },
      });
      fireEvent.click(screen.getByRole("button", { name: /create operator/i }));

      await waitFor(() =>
        expect(
          screen.queryAllByRole("alert").some((el) =>
            el.textContent?.includes("Already exists")
          )
        ).toBe(true)
      );
    });

    test("unknown role → 422 → alert on role-select", async () => {
      setupFetch([
        { ok: true, status: 200, body: ME_WITH_PERM },
        { ok: true, status: 200, body: OPERATOR_LIST },
        { ok: true, status: 200, body: ROLES_LIST },
        { ok: false, status: 422, body: { detail: "role not found: 'ghost'" } },
      ]);
      renderWithClient();

      await waitFor(() =>
        expect(screen.getByRole("form", { name: "Create new operator" })).toBeInTheDocument()
      );

      fireEvent.change(screen.getByLabelText("Email"), {
        target: { value: "ghost@irontrust.test" },
      });
      fireEvent.change(screen.getByLabelText("Display name"), {
        target: { value: "Ghost" },
      });
      fireEvent.click(screen.getByRole("button", { name: /create operator/i }));

      await waitFor(() =>
        expect(
          screen.queryAllByRole("alert").some((el) =>
            el.textContent?.includes("Invalid role")
          )
        ).toBe(true)
      );
    });
  });
});
