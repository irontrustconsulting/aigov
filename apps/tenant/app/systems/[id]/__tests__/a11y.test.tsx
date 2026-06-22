/**
 * @jest-environment jsdom
 *
 * axe pass on the system drill-in's settled state (WCAG 2.1 AA baseline,
 * FRONTEND §4).
 */
import { render, waitFor, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import type { MeRead, SystemRollupRead } from "@irontrust/api-client";
import { expectNoAxeViolations } from "../../../../test-utils/axe";
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

const rollup: SystemRollupRead = {
  system_id: "sys-1",
  system_name: "Acme Resume Screener",
  use_case_count: 1,
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
  ],
};

const coverageMatrix = {
  scope: "system", scope_id: "sys-1", framework_filter: null, include_unapproved: false,
  controls: [], frameworks: [], unaddressed_controls: [], not_an_obligation_set: false,
  generated_at: "2026-06-22T12:00:00Z",
};

afterEach(() => jest.restoreAllMocks());

test("SystemDetailClient axe pass", async () => {
  global.fetch = jest.fn((input: RequestInfo | URL) => {
    const url = String(input);
    let body: unknown;
    if (url.includes("/v1/me")) body = me(["authoriser"]);
    else if (url.includes("/coverage")) body = coverageMatrix;
    else body = rollup;
    return Promise.resolve({
      ok: true,
      status: 200,
      text: async () => JSON.stringify(body),
    } as Response);
  }) as jest.Mock;

  const { container } = render(<SystemDetailClient systemId="sys-1" />, { wrapper });
  await waitFor(() => screen.getByText("Acme Resume Screener"));
  await expectNoAxeViolations(container);
});
