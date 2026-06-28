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

type DraftOpt = { body: Record<string, unknown> } | "none" | "error";

function mockFetch(opts: {
  me: MeRead;
  portfolio?: SystemRollupRead[];
  systems?: SystemRead[];
  draft?: DraftOpt;
}) {
  global.fetch = jest.fn((input: RequestInfo | URL) => {
    const url = String(input);
    if (url.includes("/v1/draft-registrations/active")) {
      const d = opts.draft ?? "none";
      if (d === "error") {
        return Promise.resolve({ ok: false, status: 500, text: async () => "error" } as Response);
      }
      if (d === "none") {
        return Promise.resolve({ ok: true, status: 204, text: async () => "" } as Response);
      }
      return Promise.resolve({
        ok: true,
        status: 200,
        text: async () => JSON.stringify({
          id: "draft-1",
          tenant_id: "tenant-1",
          owner_user_id: "user-1",
          draft_blob: d.body,
          created_at: "2026-06-28T10:00:00Z",
          updated_at: "2026-06-28T10:00:00Z",
        }),
      } as Response);
    }
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

describe("DashboardPage — draft-resume banner (FE-29, DM-S3b)", () => {
  test("system_owner + active draft + zero systems (scaffolded-empty): banner present and links to /systems/new", async () => {
    mockFetch({
      me: me(["system_owner"]),
      portfolio: [],
      systems: [],
      draft: { body: { catalogueProductName: "ATS Pro" } },
    });

    renderWithClient();

    await waitFor(() =>
      expect(screen.getByLabelText("draft-resume")).toBeInTheDocument()
    );
    const link = screen.getByRole("link", { name: /Resume/ });
    expect(link).toHaveAttribute("href", "/systems/new");
    expect(screen.getByText("ATS Pro")).toBeInTheDocument();
  });

  test("system_owner + active draft + populated portfolio: banner present", async () => {
    mockFetch({
      me: me(["system_owner"]),
      portfolio: [pendingReviewUseCase],
      systems: [],
      draft: { body: { name: "Custom HR Tool" } },
    });

    renderWithClient();

    await waitFor(() =>
      expect(screen.getByLabelText("draft-resume")).toBeInTheDocument()
    );
    expect(screen.getByText("Custom HR Tool")).toBeInTheDocument();
  });

  test("system_owner + empty blob: renders 'Untitled registration' fallback", async () => {
    mockFetch({
      me: me(["system_owner"]),
      portfolio: [],
      systems: [],
      draft: { body: {} },
    });

    renderWithClient();

    await waitFor(() =>
      expect(screen.getByLabelText("draft-resume")).toBeInTheDocument()
    );
    expect(screen.getByText("Untitled registration")).toBeInTheDocument();
  });

  test("system_owner + no draft (204): no banner", async () => {
    mockFetch({
      me: me(["system_owner"]),
      portfolio: [],
      systems: [],
      draft: "none",
    });

    renderWithClient();

    // Wait for the page to settle
    await waitFor(() => screen.getByLabelText("systems"));
    expect(screen.queryByLabelText("draft-resume")).toBeNull();
  });

  test("system_owner + draft query error: no banner (RD-2)", async () => {
    mockFetch({
      me: me(["system_owner"]),
      portfolio: [],
      systems: [],
      draft: "error",
    });

    renderWithClient();

    await waitFor(() => screen.getByLabelText("systems"));
    expect(screen.queryByLabelText("draft-resume")).toBeNull();
  });

  test("admin (zero gov roles): no banner and GET /v1/draft-registrations/active is not requested (DF2-5)", async () => {
    const fetchSpy = (global.fetch = jest.fn(() =>
      Promise.resolve({
        ok: true,
        status: 200,
        text: async () => JSON.stringify(me([])),
      } as Response)
    )) as jest.Mock;

    renderWithClient();

    await waitFor(() => screen.getByLabelText("admin-empty-state"));
    expect(screen.queryByLabelText("draft-resume")).toBeNull();
    for (const call of fetchSpy.mock.calls) {
      expect(String(call[0])).not.toContain("/v1/draft-registrations/active");
    }
  });

  test("loading state (portfolio pending): no banner rendered (DF-S3b-1)", async () => {
    global.fetch = jest.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/v1/me")) {
        return Promise.resolve({
          ok: true,
          status: 200,
          text: async () => JSON.stringify(me(["system_owner"])),
        } as Response);
      }
      // portfolio hangs — never resolves
      return new Promise(() => {});
    }) as jest.Mock;

    renderWithClient();

    // me resolves; portfolio hangs → should be in loading skeleton, no banner
    await waitFor(() => screen.getByRole("status"));
    expect(screen.queryByLabelText("draft-resume")).toBeNull();
  });

  test("error state (portfolio errored): no banner rendered (DF-S3b-1)", async () => {
    global.fetch = jest.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/v1/me")) {
        return Promise.resolve({
          ok: true,
          status: 200,
          text: async () => JSON.stringify(me(["system_owner"])),
        } as Response);
      }
      if (url.includes("/v1/draft-registrations/active")) {
        return Promise.resolve({
          ok: true,
          status: 200,
          text: async () =>
            JSON.stringify({
              id: "draft-1",
              tenant_id: "tenant-1",
              owner_user_id: "user-1",
              draft_blob: { catalogueProductName: "ATS Pro" },
              created_at: "2026-06-28T10:00:00Z",
              updated_at: "2026-06-28T10:00:00Z",
            }),
        } as Response);
      }
      // portfolio + systems error
      return Promise.resolve({ ok: false, status: 500, text: async () => "error" } as Response);
    }) as jest.Mock;

    renderWithClient();

    await waitFor(() => screen.getByText(/could not load the portfolio/i));
    expect(screen.queryByLabelText("draft-resume")).toBeNull();
  });
});
