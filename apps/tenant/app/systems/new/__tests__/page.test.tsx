/**
 * @jest-environment jsdom
 *
 * WI-10: per-role snapshot of the wizard's entry render. system_owner gets
 * the full spine (starts at drill-down); reviewer/authoriser/auditor get
 * the assurance read-only message; a bare contributor (or any member
 * without system_owner) gets the "needs a system owner" empty-state — not
 * a dead control.
 */
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import NewSystemPage from "../page";

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

function mockMe(roleKeys: string[]) {
  global.fetch = jest.fn((input: RequestInfo | URL) => {
    const url = String(input);
    if (url.includes("/v1/me")) {
      return Promise.resolve({
        ok: true,
        status: 200,
        text: async () =>
          JSON.stringify({
            membership_id: "m1",
            tenant_id: "t1",
            role: "member",
            email: null,
            name: null,
            tenant_name: "Acme Corp",
            governance_roles: roleKeys.map((key) => ({
              id: key,
              key,
              name: key,
              description: null,
              line_of_defence: 1,
            })),
          }),
      } as Response);
    }
    // DM-S3: active-draft returns 204 (no active draft) so the wizard shows
    // the drill-down directly rather than ResumePrompt.
    if (url.includes("/v1/draft-registrations/active")) {
      return Promise.resolve({ ok: true, status: 204, text: async () => "" } as Response);
    }
    return Promise.resolve({ ok: true, status: 200, text: async () => JSON.stringify([]) } as Response);
  }) as jest.Mock;
}

afterEach(() => jest.restoreAllMocks());

describe("NewSystemPage role-aware entry render", () => {
  test("system_owner sees the full spine, starting at drill-down", async () => {
    mockMe(["system_owner"]);
    render(<NewSystemPage />, { wrapper });
    await waitFor(() => expect(screen.getByLabelText("category-drill-down")).toBeInTheDocument());
  });

  test("a bare contributor sees the needs-a-system-owner empty-state, not a dead control", async () => {
    mockMe(["contributor"]);
    render(<NewSystemPage />, { wrapper });
    await waitFor(() => expect(screen.getByLabelText("needs-system-owner")).toBeInTheDocument());
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  test("a bare member with no governance role sees the needs-a-system-owner empty-state", async () => {
    mockMe([]);
    render(<NewSystemPage />, { wrapper });
    await waitFor(() => expect(screen.getByLabelText("needs-system-owner")).toBeInTheDocument());
  });

  test.each(["reviewer", "authoriser", "auditor"])(
    "%s sees the assurance read-only message, no capture controls",
    async (roleKey) => {
      mockMe([roleKey]);
      render(<NewSystemPage />, { wrapper });
      await waitFor(() => expect(screen.getByLabelText("assurance-read-only")).toBeInTheDocument());
      expect(screen.queryByRole("button")).not.toBeInTheDocument();
    }
  );
});
