/**
 * @jest-environment jsdom
 *
 * UI-F10-CLEARANCE WI-4 done-checks (DF-CLR-10/11, INV-91).
 */
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import type { MeRead } from "@irontrust/api-client";
import { TenantSidebar } from "../tenant-sidebar";

jest.mock("next/navigation", () => ({
  usePathname: () => "/dashboard",
}));

function makeMeRead(governanceRoleKeys: string[], role = "member"): MeRead {
  return {
    membership_id: "m-1",
    tenant_id: "t-1",
    role,
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

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

function mockMe(meData: MeRead) {
  global.fetch = jest.fn(() =>
    Promise.resolve({ ok: true, status: 200, text: async () => JSON.stringify(meData) } as Response)
  ) as jest.Mock;
}

afterEach(() => jest.restoreAllMocks());

test("authoriser: no Review queue entry; Clearances entry present", async () => {
  mockMe(makeMeRead(["authoriser"]));
  render(<TenantSidebar />, { wrapper });

  await waitFor(() => expect(screen.getByText("Clearances")).toBeInTheDocument());
  expect(screen.queryByText("Review queue")).not.toBeInTheDocument();
});

test("reviewer: Review queue present; Clearances present", async () => {
  mockMe(makeMeRead(["reviewer"]));
  render(<TenantSidebar />, { wrapper });

  await waitFor(() => expect(screen.getByText("Review queue")).toBeInTheDocument());
  expect(screen.getByText("Clearances")).toBeInTheDocument();
});

test("system_owner: no Review queue; Clearances present", async () => {
  mockMe(makeMeRead(["system_owner"]));
  render(<TenantSidebar />, { wrapper });

  await waitFor(() => expect(screen.getByText("Clearances")).toBeInTheDocument());
  expect(screen.queryByText("Review queue")).not.toBeInTheDocument();
});

test("auditor: no Review queue; Clearances present", async () => {
  mockMe(makeMeRead(["auditor"]));
  render(<TenantSidebar />, { wrapper });

  await waitFor(() => expect(screen.getByText("Clearances")).toBeInTheDocument());
  expect(screen.queryByText("Review queue")).not.toBeInTheDocument();
});

test("admin (zero governance roles): neither Review queue nor Clearances; Portfolio always present", async () => {
  mockMe(makeMeRead([], "admin"));
  render(<TenantSidebar />, { wrapper });

  // Wait for the /v1/me fetch to resolve — Members only appears once data loads.
  await waitFor(() => expect(screen.getByText("Members")).toBeInTheDocument());
  expect(screen.getByText("Portfolio")).toBeInTheDocument();
  expect(screen.queryByText("Review queue")).not.toBeInTheDocument();
  expect(screen.queryByText("Clearances")).not.toBeInTheDocument();
});
