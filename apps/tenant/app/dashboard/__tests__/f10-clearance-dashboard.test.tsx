/**
 * @jest-environment jsdom
 *
 * UI-F10-CLEARANCE WI-5/WI-6 done-checks (dashboard your-court/posture
 * re-treatment). F2 contract-preservation checks already live in
 * f2-portfolio.test.tsx; this file covers only what's new.
 */
import { render, screen, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { GateResultRead, MeRead, SystemRead, SystemRollupRead } from "@irontrust/api-client";
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

function blocking(overrides: Partial<GateResultRead>): GateResultRead {
  return {
    state: "vendor_check",
    verdict: "park",
    reason_code: "vendor_not_started",
    reason: "Vendor clearance not yet requested",
    responsible_party: "authoriser",
    ...overrides,
  } as GateResultRead;
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
    return Promise.resolve({ ok: true, status: 200, text: async () => JSON.stringify(body) } as Response);
  }) as jest.Mock;
}

afterEach(() => jest.restoreAllMocks());

describe("WI-5: your-court forward routing (DF-CLR-13/V-a)", () => {
  test("an authoriser-court row blocked on the vendor gate links to /clearances", async () => {
    const portfolio: SystemRollupRead[] = [
      {
        system_id: "sys-1",
        system_name: "Risk Assessment Tool",
        use_case_count: 1,
        highest_tier: "high_risk",
        use_cases: [
          {
            use_case_id: "uc-1",
            title: "Credit scoring",
            state: "vendor_check",
            eu_tier: "high_risk",
            blocking: blocking({ reason_code: "vendor_not_started" }),
          },
        ],
      } as unknown as SystemRollupRead,
    ];
    mockFetch({ me: me(["authoriser"]), portfolio, systems: [{ id: "sys-1" } as SystemRead] });
    renderWithClient();

    await waitFor(() => expect(screen.getByLabelText("your-court")).toBeInTheDocument());
    const region = screen.getByLabelText("your-court");
    const link = within(region).getByText("Credit scoring").closest("a");
    expect(link).toHaveAttribute("href", "/clearances");
  });

  test("an authoriser-court row blocked on deployment-authorisation (not a clearance gate) routes to /use-cases/{id}", async () => {
    const portfolio: SystemRollupRead[] = [
      {
        system_id: "sys-1",
        system_name: "Risk Assessment Tool",
        use_case_count: 1,
        highest_tier: "high_risk",
        use_cases: [
          {
            use_case_id: "uc-1",
            title: "Credit scoring",
            state: "pending_authorisation",
            eu_tier: "high_risk",
            blocking: blocking({
              state: "pending_authorisation",
              reason_code: "no_current_authorisation",
            }),
          },
        ],
      } as unknown as SystemRollupRead,
    ];
    mockFetch({ me: me(["authoriser"]), portfolio, systems: [{ id: "sys-1" } as SystemRead] });
    renderWithClient();

    await waitFor(() => expect(screen.getByLabelText("your-court")).toBeInTheDocument());
    const region = screen.getByLabelText("your-court");
    const link = within(region).getByText("Credit scoring").closest("a");
    expect(link).toHaveAttribute("href", "/use-cases/uc-1");
  });

  test("reviewer-court and owner-court rows route to /use-cases/{id}", async () => {
    const portfolio: SystemRollupRead[] = [
      {
        system_id: "sys-owner",
        system_name: "Owner System",
        use_case_count: 1,
        highest_tier: "high_risk",
        use_cases: [
          {
            use_case_id: "uc-owner",
            title: "Owner task",
            state: "intake",
            eu_tier: "high_risk",
            blocking: blocking({ state: "intake", reason_code: "no_aiia", responsible_party: "user" }),
          },
        ],
      } as unknown as SystemRollupRead,
      {
        system_id: "sys-reviewer",
        system_name: "Reviewer System",
        use_case_count: 1,
        highest_tier: "high_risk",
        use_cases: [
          {
            use_case_id: "uc-reviewer",
            title: "Reviewer task",
            state: "under_assessment",
            eu_tier: "high_risk",
            blocking: blocking({
              state: "under_assessment",
              reason_code: "tier_not_ratified",
              responsible_party: "reviewer",
            }),
          },
        ],
      } as unknown as SystemRollupRead,
    ];
    mockFetch({
      me: me(["system_owner", "reviewer"]),
      portfolio,
      systems: [{ id: "sys-owner" } as SystemRead, { id: "sys-reviewer" } as SystemRead],
    });
    renderWithClient();

    await waitFor(() => expect(screen.getByLabelText("your-court")).toBeInTheDocument());
    const region = screen.getByLabelText("your-court");
    expect(within(region).getByText("Owner task").closest("a")).toHaveAttribute(
      "href",
      "/use-cases/uc-owner"
    );
    expect(within(region).getByText("Reviewer task").closest("a")).toHaveAttribute(
      "href",
      "/use-cases/uc-reviewer"
    );
  });

  test("no em-dash in the your-court DOM", async () => {
    const portfolio: SystemRollupRead[] = [
      {
        system_id: "sys-1",
        system_name: "Risk Assessment Tool",
        use_case_count: 1,
        highest_tier: "high_risk",
        use_cases: [
          {
            use_case_id: "uc-1",
            title: "Credit scoring",
            state: "vendor_check",
            eu_tier: "high_risk",
            blocking: blocking({}),
          },
        ],
      } as unknown as SystemRollupRead,
    ];
    mockFetch({ me: me(["authoriser"]), portfolio, systems: [{ id: "sys-1" } as SystemRead] });
    renderWithClient();

    await waitFor(() => expect(screen.getByLabelText("your-court")).toBeInTheDocument());
    const region = screen.getByLabelText("your-court");
    expect(region.textContent).not.toMatch(/—/);
  });

  test("VerdictChip is present per your-court row", async () => {
    const portfolio: SystemRollupRead[] = [
      {
        system_id: "sys-1",
        system_name: "Risk Assessment Tool",
        use_case_count: 1,
        highest_tier: "high_risk",
        use_cases: [
          {
            use_case_id: "uc-1",
            title: "Credit scoring",
            state: "vendor_check",
            eu_tier: "high_risk",
            blocking: blocking({}),
          },
        ],
      } as unknown as SystemRollupRead,
    ];
    mockFetch({ me: me(["authoriser"]), portfolio, systems: [{ id: "sys-1" } as SystemRead] });
    const { container } = renderWithClient();

    await waitFor(() => expect(screen.getByLabelText("your-court")).toBeInTheDocument());
    const region = container.querySelector("[aria-label='your-court']")!;
    expect(region.querySelector("[data-tone]")).not.toBeNull();
  });
});

describe("WI-6: posture distribution strip", () => {
  test("distribution counts equal the client-side tally of use_cases[].state", async () => {
    const portfolio: SystemRollupRead[] = [
      {
        system_id: "sys-1",
        system_name: "System A",
        use_case_count: 2,
        highest_tier: "high_risk",
        use_cases: [
          {
            use_case_id: "uc-1",
            title: "UC1",
            state: "vendor_check",
            eu_tier: "high_risk",
            blocking: blocking({ responsible_party: "authoriser" }),
          },
          {
            use_case_id: "uc-2",
            title: "UC2",
            state: "vendor_check",
            eu_tier: "high_risk",
            blocking: blocking({ responsible_party: "authoriser" }),
          },
        ],
      } as unknown as SystemRollupRead,
      {
        system_id: "sys-2",
        system_name: "System B",
        use_case_count: 1,
        highest_tier: "high_risk",
        use_cases: [
          {
            use_case_id: "uc-3",
            title: "UC3",
            state: "under_assessment",
            eu_tier: "high_risk",
            blocking: blocking({ state: "under_assessment", responsible_party: "user" }),
          },
        ],
      } as unknown as SystemRollupRead,
    ];
    mockFetch({
      me: me(["reviewer"]),
      portfolio,
      systems: [{ id: "sys-1" } as SystemRead, { id: "sys-2" } as SystemRead],
    });
    const { container } = renderWithClient();

    await waitFor(() => expect(screen.getByLabelText("portfolio-posture")).toBeInTheDocument());
    const strip = container.querySelector("[aria-label='lifecycle-state distribution']")!;
    // 2 use cases at vendor_check, 1 at under_assessment.
    expect(strip.textContent).toContain("2");
    expect(strip.textContent).toContain("1");
  });

  test("audit affordance present and links to /audit", async () => {
    mockFetch({
      me: me(["reviewer"]),
      portfolio: [
        {
          system_id: "sys-1",
          system_name: "System A",
          use_case_count: 1,
          highest_tier: "high_risk",
          use_cases: [
            {
              use_case_id: "uc-1",
              title: "UC1",
              state: "vendor_check",
              eu_tier: "high_risk",
              blocking: blocking({}),
            },
          ],
        } as unknown as SystemRollupRead,
      ],
      systems: [{ id: "sys-1" } as SystemRead],
    });
    renderWithClient();

    await waitFor(() => expect(screen.getByLabelText("portfolio-posture")).toBeInTheDocument());
    const link = screen.getByRole("link", { name: /view control coverage and audit packs/i });
    expect(link).toHaveAttribute("href", "/audit");
  });
});
