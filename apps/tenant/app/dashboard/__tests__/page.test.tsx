/**
 * @jest-environment jsdom
 */
import { render, screen, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { MeRead, SystemRead, SystemRollupRead } from "@irontrust/api-client";
import DashboardPage from "../page";

function renderWithClient() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <DashboardPage />
    </QueryClientProvider>
  );
}

function me(governanceRoleKeys: string[]): MeRead {
  return {
    membership_id: "m1",
    tenant_id: "tenant-1",
    role: "member",
    email: "caller@acme.test",
    name: "Caller",
    tenant_name: "Acme Corp",
    governance_roles: governanceRoleKeys.map((key) => ({
      id: key,
      key,
      name: key,
      description: null,
      line_of_defence: 1,
    })),
  };
}

function mockFetch(opts: { me: MeRead; portfolio?: SystemRollupRead[]; systems?: SystemRead[] }) {
  global.fetch = jest.fn((input: RequestInfo | URL) => {
    const url = String(input);
    const body = url.includes("/v1/me")
      ? opts.me
      : url.includes("/v1/portfolio")
        ? (opts.portfolio ?? [])
        : url.includes("/v1/systems")
          ? (opts.systems ?? [])
          : null;
    return Promise.resolve({
      ok: true,
      status: 200,
      text: async () => JSON.stringify(body),
    } as Response);
  }) as jest.Mock;
}

afterEach(() => jest.restoreAllMocks());

const pendingReviewUseCase: SystemRollupRead = {
  system_id: "sys-1",
  system_name: "Acme Resume Screener",
  use_case_count: 1,
  highest_tier: "requires_context",
  use_cases: [
    {
      use_case_id: "uc-1",
      title: "Screen candidate applications",
      state: "intake",
      eu_tier: "requires_context",
      blocking: {
        state: "intake",
        verdict: "park",
        reason_code: "tier_not_ratified",
        reason: "Classification tier not yet ratified (eu_tier pending)",
        responsible_party: "reviewer",
      },
    },
  ],
};

describe("DashboardPage (UI-F2-PORTFOLIO portfolio landing)", () => {
  test("admin-only caller (zero governance roles) sees the admin/empty state and issues no gov:ALL request", async () => {
    const fetchSpy = (global.fetch = jest.fn(() =>
      Promise.resolve({
        ok: true,
        status: 200,
        text: async () => JSON.stringify(me([])),
      } as Response)
    )) as jest.Mock;

    renderWithClient();

    await waitFor(() => expect(screen.getByLabelText("admin-empty-state")).toBeInTheDocument());

    for (const call of fetchSpy.mock.calls) {
      const url = String(call[0]);
      expect(url.includes("/v1/portfolio")).toBe(false);
      expect(url.includes("/v1/systems")).toBe(false);
    }
  });

  test("a PENDING_REVIEW REQUIRES_CONTEXT use case is the reviewer's court, not the owner's (B1 regression)", async () => {
    mockFetch({ me: me(["reviewer"]), portfolio: [pendingReviewUseCase], systems: [] });

    renderWithClient();

    await waitFor(() => expect(screen.getByLabelText("your-court")).toBeInTheDocument());
    const yourCourt = screen.getByLabelText("your-court");
    expect(within(yourCourt).getByText(/screen candidate applications/i)).toBeInTheDocument();
    expect(within(yourCourt).getByText(/tier not yet ratified/i)).toBeInTheDocument();
  });

  test("the same PENDING_REVIEW use case is NOT the system_owner's court", async () => {
    mockFetch({ me: me(["system_owner"]), portfolio: [pendingReviewUseCase], systems: [] });

    renderWithClient();

    await waitFor(() => expect(screen.getByLabelText("your-court")).toBeInTheDocument());
    expect(screen.getByText(/nothing is waiting on you/i)).toBeInTheDocument();
  });

  test("auditor leads with portfolio posture, and their (empty) your-court set never matches — 3rd line, never a blocking party", async () => {
    mockFetch({ me: me(["auditor"]), portfolio: [pendingReviewUseCase], systems: [] });

    renderWithClient();

    await waitFor(() => expect(screen.getByLabelText("portfolio-posture")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByLabelText("your-court")).toBeInTheDocument());
    expect(screen.getByText(/nothing is waiting on you/i)).toBeInTheDocument();
  });

  test("a zero-use-case system (A2) renders as a non-interactive nudge card, not a court row", async () => {
    mockFetch({
      me: me(["system_owner"]),
      portfolio: [],
      systems: [
        {
          id: "sys-2",
          tenant_id: "tenant-1",
          name: "New CRM Integration",
          is_custom: true,
          lifecycle_stage: null,
          created_at: "2026-01-01T00:00:00Z",
          updated_at: "2026-01-01T00:00:00Z",
        },
      ],
    });

    renderWithClient();

    await waitFor(() => expect(screen.getByLabelText("zero-use-case-system")).toBeInTheDocument());
    expect(screen.getByText(/no use case registered yet/i)).toBeInTheDocument();
  });
});
