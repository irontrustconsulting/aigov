/**
 * @jest-environment jsdom
 *
 * F2 done-checks (UI-C1-PORTFOLIO-IDENTITY composition pass):
 * - Whose-court section leads for adoption face (system_owner)
 * - Portfolio posture section leads for assurance face (reviewer)
 * - No compliance-% headline (INV-52)
 * - Compact TierBadge rendered in use-case list (not raw tier string)
 * - Zero-states: admin-empty, first-run (zero systems), per-region empty your-court
 * - Loading → Skeleton (role=status); Error → "Try again" retry button
 * - No /v1/coverage or /v1/export call from the dashboard (DF6-9)
 */
import { render, screen, waitFor } from "@testing-library/react";
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
  } as unknown as MeRead;
}

const HIGH_RISK_SYSTEM: SystemRollupRead = {
  system_id: "sys-1",
  system_name: "Risk Assessment Tool",
  use_case_count: 1,
  highest_tier: "high_risk",
  use_cases: [
    {
      use_case_id: "uc-1",
      title: "Credit scoring",
      state: "under_assessment",
      eu_tier: "high_risk",
      blocking: {
        state: "under_assessment",
        verdict: "park",
        reason_code: "awaiting_review",
        reason: "Awaiting review",
        responsible_party: "reviewer",
      },
    },
  ],
} as unknown as SystemRollupRead;

const SYSTEM_READ: SystemRead = {
  id: "sys-1",
  name: "Risk Assessment Tool",
  use_case_count: 1,
} as unknown as SystemRead;

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

afterEach(() => { jest.restoreAllMocks(); });

describe("F2 dashboard — whose-court leads for adoption face", () => {
  test("system_owner: whose-court section appears before portfolio-posture", async () => {
    mockFetch({ me: me(["system_owner"]), portfolio: [HIGH_RISK_SYSTEM], systems: [SYSTEM_READ] });
    renderWithClient();
    await waitFor(() => expect(screen.getByLabelText("your-court")).toBeInTheDocument());
    // PageScaffold renders a <div>, not <main> (AppShell provides <main> in the live app).
    const root = document.body;
    const yourCourtEl = root.querySelector("[aria-label='your-court']")!;
    const postureEl = root.querySelector("[aria-label='portfolio-posture']")!;
    // your-court should come first: postureEl follows yourCourtEl
    expect(
      yourCourtEl.compareDocumentPosition(postureEl) & Node.DOCUMENT_POSITION_FOLLOWING
    ).not.toBe(0);
  });

  test("reviewer: portfolio-posture section appears before your-court", async () => {
    mockFetch({ me: me(["reviewer"]), portfolio: [HIGH_RISK_SYSTEM], systems: [SYSTEM_READ] });
    renderWithClient();
    await waitFor(() => expect(screen.getByLabelText("portfolio-posture")).toBeInTheDocument());
    // PageScaffold renders a <div>, not <main> (AppShell provides <main> in the live app).
    const root = document.body;
    const postureEl = root.querySelector("[aria-label='portfolio-posture']")!;
    const yourCourtEl = root.querySelector("[aria-label='your-court']")!;
    // posture-section should come first: yourCourtEl follows postureEl
    expect(
      postureEl.compareDocumentPosition(yourCourtEl) & Node.DOCUMENT_POSITION_FOLLOWING
    ).not.toBe(0);
  });
});

describe("F2 dashboard — no compliance-% (INV-52)", () => {
  test("no percentage text in DOM", async () => {
    mockFetch({ me: me(["system_owner"]), portfolio: [HIGH_RISK_SYSTEM], systems: [SYSTEM_READ] });
    renderWithClient();
    await waitFor(() => expect(screen.getByLabelText("your-court")).toBeInTheDocument());
    expect(document.body.textContent).not.toMatch(/\d+%/);
  });
});

describe("F2 dashboard — compact TierBadge in use-case list", () => {
  test("renders TierBadge with data-variant=compact for a use case with eu_tier=high_risk", async () => {
    mockFetch({ me: me(["system_owner"]), portfolio: [HIGH_RISK_SYSTEM], systems: [SYSTEM_READ] });
    const { container } = renderWithClient();
    await waitFor(() => expect(screen.getByLabelText("your-court")).toBeInTheDocument());
    const badge = container.querySelector("[data-variant='compact'][data-tier='high']");
    expect(badge).not.toBeNull();
  });
});

describe("F2 dashboard — zero-states (INV-70)", () => {
  test("admin (zero gov roles) — EmptyState shown; no portfolio or systems call", async () => {
    const fetchSpy = (global.fetch = jest.fn(() =>
      Promise.resolve({
        ok: true,
        status: 200,
        text: async () => JSON.stringify(me([])),
      } as Response)
    ) as jest.Mock);
    renderWithClient();
    await waitFor(() => expect(screen.getByLabelText("admin-empty-state")).toBeInTheDocument());
    for (const call of fetchSpy.mock.calls) {
      expect(String(call[0])).not.toContain("/v1/portfolio");
      expect(String(call[0])).not.toContain("/v1/systems");
    }
  });

  test("governance caller with zero systems — FirstRunPanel shown", async () => {
    mockFetch({ me: me(["system_owner"]), portfolio: [], systems: [] });
    renderWithClient();
    await waitFor(() =>
      expect(screen.getByRole("heading", { name: /register your first ai system/i })).toBeInTheDocument()
    );
  });

  test("your-court section shows EmptyState when no items awaiting", async () => {
    // system_owner: HIGH_RISK_SYSTEM blocks on 'reviewer', so owner's court is empty.
    mockFetch({ me: me(["system_owner"]), portfolio: [HIGH_RISK_SYSTEM], systems: [SYSTEM_READ] });
    renderWithClient();
    await waitFor(() => expect(screen.getByLabelText("your-court")).toBeInTheDocument());
    expect(screen.getByText(/nothing is waiting on you/i)).toBeInTheDocument();
  });
});

describe("F2 dashboard — loading and error states (INV-70)", () => {
  test("loading state renders Skeleton (role=status)", () => {
    // Never resolve fetch — stays in loading state.
    global.fetch = jest.fn(() => new Promise(() => {})) as jest.Mock;
    const { container } = renderWithClient();
    // Skeleton renders role=status
    expect(container.querySelector("[role='status']")).toBeInTheDocument();
  });

  test("error state renders Try again button", async () => {
    global.fetch = jest.fn(() =>
      Promise.resolve({ ok: false, status: 500, text: async () => "" } as Response)
    ) as jest.Mock;
    renderWithClient();
    await waitFor(() => expect(screen.getByRole("button", { name: /try again/i })).toBeInTheDocument());
  });
});

describe("F2 dashboard — no coverage or export call from dashboard (DF6-9)", () => {
  test("no /v1/coverage or /v1/export request issued", async () => {
    mockFetch({ me: me(["system_owner"]), portfolio: [HIGH_RISK_SYSTEM], systems: [SYSTEM_READ] });
    renderWithClient();
    await waitFor(() => expect(screen.getByLabelText("your-court")).toBeInTheDocument());
    for (const call of (global.fetch as jest.Mock).mock.calls) {
      const url = String(call[0]);
      expect(url).not.toContain("/v1/coverage");
      expect(url).not.toContain("/v1/export");
    }
  });
});
