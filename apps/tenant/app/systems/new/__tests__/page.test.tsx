/**
 * @jest-environment jsdom
 *
 * WI-10: per-role snapshot of the wizard's entry render. system_owner gets
 * the full spine (starts at drill-down); reviewer/authoriser/auditor get
 * the assurance read-only message; a bare contributor (or any member
 * without system_owner) gets the "needs a system owner" empty-state — not
 * a dead control.
 */
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
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

/** UI-DRAFT-RESUME-GATE: mockMe variant with control over the active-draft
 * response and DELETE/POST/PATCH on /v1/draft-registrations. */
function mockMeWithDraft(
  roleKeys: string[],
  activeDraftMode: "none" | "present" | "error",
  draftOverrides?: Record<string, unknown>
) {
  const draftRow = {
    id: "draft-1",
    tenant_id: "t1",
    owner_user_id: "u1",
    draft_blob: { step: "intake", catalogueProductName: "Widget Assistant" },
    created_at: "2026-07-01T00:00:00Z",
    updated_at: "2026-07-01T00:00:00Z",
    ...draftOverrides,
  };
  global.fetch = jest.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    const method = init?.method ?? "GET";
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
    if (url.includes("/v1/draft-registrations/active")) {
      if (activeDraftMode === "error") {
        return Promise.resolve({ ok: false, status: 500, text: async () => "" } as Response);
      }
      if (activeDraftMode === "present") {
        return Promise.resolve({ ok: true, status: 200, text: async () => JSON.stringify(draftRow) } as Response);
      }
      return Promise.resolve({ ok: true, status: 204, text: async () => "" } as Response);
    }
    if (url.includes("/v1/draft-registrations") && method === "DELETE") {
      return Promise.resolve({ ok: true, status: 204, text: async () => "" } as Response);
    }
    if (url.includes("/v1/draft-registrations") && (method === "POST" || method === "PATCH")) {
      return Promise.resolve({ ok: true, status: 200, text: async () => JSON.stringify(draftRow) } as Response);
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

describe("NewSystemPage draft resume/discard front-door (UI-DRAFT-RESUME-GATE, INV-85)", () => {
  test("(a) system_owner with an active draft on fresh mount sees ResumePrompt, not a wizard step", async () => {
    mockMeWithDraft(["system_owner"], "present");
    render(<NewSystemPage />, { wrapper });
    await waitFor(() => expect(screen.getByText(/Continue registering/)).toBeInTheDocument());
    expect(screen.queryByLabelText("category-drill-down")).not.toBeInTheDocument();
  });

  test("(b) Resume renders the wizard at the saved step and dismisses ResumePrompt", async () => {
    mockMeWithDraft(["system_owner"], "present");
    render(<NewSystemPage />, { wrapper });
    await waitFor(() => expect(screen.getByText(/Continue registering/)).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "Resume" }));
    await waitFor(() => expect(screen.getByLabelText("intake-capture")).toBeInTheDocument());
    expect(screen.queryByText(/Continue registering/)).not.toBeInTheDocument();
  });

  test("(c) Discard confirm calls discard.mutate with the draft id and returns to a fresh drill-down", async () => {
    mockMeWithDraft(["system_owner"], "present");
    render(<NewSystemPage />, { wrapper });
    await waitFor(() => expect(screen.getByText(/Continue registering/)).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "Discard" }));
    fireEvent.click(screen.getByRole("button", { name: "Discard" }));
    await waitFor(() =>
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining("/v1/draft-registrations/draft-1"),
        expect.objectContaining({ method: "DELETE" })
      )
    );
    await waitFor(() => expect(screen.getByLabelText("category-drill-down")).toBeInTheDocument());
    expect(screen.queryByText(/Continue registering/)).not.toBeInTheDocument();
  });

  test("(d) regression: ResumePrompt does not reappear after a fresh registration advances past drill-down", async () => {
    mockMeWithDraft(["system_owner"], "none");
    render(<NewSystemPage />, { wrapper });
    await waitFor(() => expect(screen.getByLabelText("category-drill-down")).toBeInTheDocument());
    fireEvent.click(screen.getByText("Not in catalogue / in-house"));
    await waitFor(() => expect(screen.getByLabelText("intake-capture")).toBeInTheDocument());
    expect(screen.queryByText(/Continue registering/)).not.toBeInTheDocument();
  });

  test("(e) activeDraft.isError renders the wizard, no front-door", async () => {
    mockMeWithDraft(["system_owner"], "error");
    render(<NewSystemPage />, { wrapper });
    await waitFor(() => expect(screen.getByLabelText("category-drill-down")).toBeInTheDocument());
    expect(screen.queryByText(/Continue registering/)).not.toBeInTheDocument();
  });
});
