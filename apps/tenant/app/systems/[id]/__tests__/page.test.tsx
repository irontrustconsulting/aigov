/**
 * @jest-environment jsdom
 */
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import type { MeRead, SystemRollupRead } from "@irontrust/api-client";
import { SystemDetailClient } from "../system-detail-client";

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
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
  };
}

const coverageMatrix = {
  scope: "system", scope_id: "sys-1", framework_filter: null, include_unapproved: false,
  controls: [], frameworks: [], unaddressed_controls: [], not_an_obligation_set: false,
  generated_at: "2026-06-22T12:00:00Z",
};

function mockFetch(meBody: MeRead, rollupData: SystemRollupRead) {
  global.fetch = jest.fn((input: RequestInfo | URL) => {
    const url = String(input);
    let body: unknown;
    if (url.includes("/v1/me")) body = meBody;
    else if (url.includes("/coverage")) body = coverageMatrix;
    else if (url.includes("/export")) body = { system_id: "sys-1", system: {}, use_cases: [], system_coverage: coverageMatrix, audit_trail: [], generated_at: "2026-06-22T12:00:00Z", content_hash: "abc" };
    else body = rollupData;
    return Promise.resolve({ ok: true, status: 200, text: async () => JSON.stringify(body) } as Response);
  }) as jest.Mock;
}

function fetchedUrls(): string[] {
  return (global.fetch as jest.Mock).mock.calls.map(([url]: [RequestInfo | URL]) => String(url));
}

afterEach(() => jest.restoreAllMocks());

const rollup: SystemRollupRead = {
  system_id: "sys-1",
  system_name: "Acme Resume Screener",
  use_case_count: 2,
  highest_tier: "high_risk",
  use_cases: [
    {
      use_case_id: "uc-1",
      title: "Screen candidate applications",
      state: "vendor_check",
      eu_tier: "high_risk",
      blocking: {
        state: "vendor_check",
        verdict: "park",
        reason_code: "vendor_not_started",
        reason: "Vendor clearance not yet requested",
        responsible_party: "authoriser",
      },
    },
    {
      use_case_id: "uc-2",
      title: "Internal candidate ranking",
      state: "under_assessment",
      eu_tier: "high_risk",
      blocking: null,
    },
  ],
};

describe("SystemDetailClient (UI-F2-PORTFOLIO drill-in)", () => {
  test("renders the rollup: system name, use cases, states, and resolved court", async () => {
    mockFetch(me(["authoriser"]), rollup);

    render(<SystemDetailClient systemId="sys-1" />, { wrapper });

    await waitFor(() => expect(screen.getByText("Acme Resume Screener")).toBeInTheDocument());
    expect(screen.getByText(/screen candidate applications/i)).toBeInTheDocument();
    expect(screen.getByText(/vendor clearance not yet requested/i)).toBeInTheDocument();
    expect(screen.getByText(/internal candidate ranking/i)).toBeInTheDocument();
    expect(screen.getByText(/nothing is blocking this use case/i)).toBeInTheDocument();
  });

  test("V-4: each use case title links to its /use-cases/{id} surface (forward link added by UI-F3-ASSESS)", async () => {
    mockFetch(me(["authoriser"]), rollup);

    render(<SystemDetailClient systemId="sys-1" />, { wrapper });

    await waitFor(() => expect(screen.getByText("Acme Resume Screener")).toBeInTheDocument());
    const links = screen.getAllByRole("link");
    expect(links).toHaveLength(rollup.use_cases.length);
    expect(links[0]).toHaveAttribute("href", `/use-cases/${rollup.use_cases[0].use_case_id}`);
  });
});

describe("SystemDetailClient (UI-F6-AUDITPACK coverage + export)", () => {
  test("admin (zero gov roles): no coverage call issued", async () => {
    mockFetch(me([]), rollup);
    render(<SystemDetailClient systemId="sys-1" />, { wrapper });
    await waitFor(() => expect(screen.getByText("Acme Resume Screener")).toBeInTheDocument());
    expect(fetchedUrls().filter((u) => u.includes("/coverage"))).toHaveLength(0);
  });

  test("gov role: coverage panel rendered after load", async () => {
    mockFetch(me(["auditor"]), rollup);
    render(<SystemDetailClient systemId="sys-1" />, { wrapper });
    await waitFor(() =>
      expect(screen.getByRole("region", { name: /system-coverage/i })).toBeInTheDocument()
    );
    expect(fetchedUrls().filter((u) => u.includes("/v1/systems/sys-1/coverage"))).toHaveLength(1);
  });

  test("system export: not fired on mount; fires only on button click (INV-53)", async () => {
    mockFetch(me(["auditor"]), rollup);
    render(<SystemDetailClient systemId="sys-1" />, { wrapper });
    await waitFor(() =>
      expect(screen.getByRole("region", { name: /system-export/i })).toBeInTheDocument()
    );
    // No export on mount
    expect(fetchedUrls().filter((u) => u.includes("/export"))).toHaveLength(0);

    fireEvent.click(screen.getByRole("button", { name: /generate system audit pack/i }));

    await waitFor(() =>
      expect(fetchedUrls().filter((u) => u.includes("/systems/sys-1/export"))).toHaveLength(1)
    );
  });
});
