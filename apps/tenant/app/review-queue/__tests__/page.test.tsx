/**
 * @jest-environment jsdom
 *
 * UI-F4-ASSURE WI-1 — review queue role-gate assertions.
 * Reviewer: sees queue entries and links to /use-cases/{id}.
 * Non-reviewer (auditor, admin): renders empty-state with no /review-queue call.
 */
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import type { MeRead, ReviewQueueEntryRead } from "@irontrust/api-client";
import { ReviewQueueClient } from "../review-queue-client";

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

function me(governanceRoleKeys: string[]): MeRead {
  return {
    membership_id: "m1",
    tenant_id: "t1",
    role: "member",
    email: "user@acme.test",
    name: "Test User",
    governance_roles: governanceRoleKeys.map((key) => ({
      id: key,
      key,
      name: key,
      description: null,
      line_of_defence: 1,
    })),
  };
}

const queueEntries: ReviewQueueEntryRead[] = [
  {
    assessment_id: "ass-1",
    use_case_id: "uc-1",
    tier_snapshot: "high_risk",
    submitted_by_name: "Alice Owner",
    submitted_by_email: "alice@acme.test",
    submitted_at: "2026-06-01T10:00:00Z",
  },
];

function mockFetch(meBody: MeRead, queue: ReviewQueueEntryRead[] = []) {
  global.fetch = jest.fn((input: RequestInfo | URL) => {
    const url = String(input);
    const body = url.includes("/v1/me") ? meBody : queue;
    return Promise.resolve({
      ok: true,
      status: 200,
      text: async () => JSON.stringify(body),
    } as Response);
  }) as jest.Mock;
}

afterEach(() => jest.restoreAllMocks());

describe("ReviewQueueClient (UI-F4-ASSURE WI-1)", () => {
  test("reviewer: renders queue entries with links to /use-cases/{id}", async () => {
    mockFetch(me(["reviewer"]), queueEntries);

    render(<ReviewQueueClient />, { wrapper });

    await waitFor(() =>
      expect(screen.getByRole("link", { name: /review use case/i })).toBeInTheDocument()
    );

    const link = screen.getByRole("link", { name: /review use case/i });
    expect(link).toHaveAttribute("href", `/use-cases/${queueEntries[0].use_case_id}`);
    expect(screen.getByText(/alice owner/i)).toBeInTheDocument();
  });

  test("reviewer: empty queue renders empty-state message", async () => {
    mockFetch(me(["reviewer"]), []);

    render(<ReviewQueueClient />, { wrapper });

    await waitFor(() =>
      expect(screen.getByText(/no assessments are awaiting/i)).toBeInTheDocument()
    );
  });

  test("auditor: renders access-denied state; no /review-queue request fired", async () => {
    mockFetch(me(["auditor"]));

    render(<ReviewQueueClient />, { wrapper });

    await waitFor(() =>
      expect(screen.getByText(/don't have reviewer access/i)).toBeInTheDocument()
    );

    const calls = (global.fetch as jest.Mock).mock.calls.map(([url]: [RequestInfo | URL]) => String(url));
    const queueCalls = calls.filter((u) => u.includes("/review-queue"));
    expect(queueCalls).toHaveLength(0);
  });

  test("admin: renders access-denied state; no /review-queue request fired", async () => {
    mockFetch(me([]));

    render(<ReviewQueueClient />, { wrapper });

    await waitFor(() =>
      expect(screen.getByText(/don't have reviewer access/i)).toBeInTheDocument()
    );

    const calls = (global.fetch as jest.Mock).mock.calls.map(([url]: [RequestInfo | URL]) => String(url));
    const queueCalls = calls.filter((u) => u.includes("/review-queue"));
    expect(queueCalls).toHaveLength(0);
  });
});
