/**
 * @jest-environment jsdom
 *
 * F2 visual done-checks (UI-V1-TENANT-SKIN):
 * - Whose-court section leads for adoption face (system_owner)
 * - Portfolio posture section leads for assurance face (reviewer)
 * - No compliance-% headline (INV-52)
 * - Compact TierBadge rendered in use-case list (not raw tier string)
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
    const main = document.querySelector("main")!;
    const yourCourtEl = main.querySelector("[aria-label='your-court']")!;
    const postureEl = main.querySelector("[aria-label='portfolio-posture']")!;
    // your-court should come first: postureEl follows yourCourtEl
    expect(
      yourCourtEl.compareDocumentPosition(postureEl) & Node.DOCUMENT_POSITION_FOLLOWING
    ).not.toBe(0);
  });

  test("reviewer: portfolio-posture section appears before your-court", async () => {
    mockFetch({ me: me(["reviewer"]), portfolio: [HIGH_RISK_SYSTEM], systems: [SYSTEM_READ] });
    renderWithClient();
    await waitFor(() => expect(screen.getByLabelText("portfolio-posture")).toBeInTheDocument());
    const main = document.querySelector("main")!;
    const postureEl = main.querySelector("[aria-label='portfolio-posture']")!;
    const yourCourtEl = main.querySelector("[aria-label='your-court']")!;
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
