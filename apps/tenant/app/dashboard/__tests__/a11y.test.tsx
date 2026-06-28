/**
 * @jest-environment jsdom
 *
 * axe pass on the portfolio landing's settled states (WCAG 2.1 AA baseline,
 * FRONTEND §4) — the deterministic, CI-friendly half of the a11y bar.
 */
import { render, waitFor, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import type { MeRead, SystemRollupRead } from "@irontrust/api-client";
import { expectNoAxeViolations } from "../../../test-utils/axe";
import DashboardPage from "../page";

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

function mockFetch(opts: {
  me: MeRead;
  portfolio?: SystemRollupRead[];
  systems?: unknown[];
  draft?: Record<string, unknown> | "none";
}) {
  global.fetch = jest.fn((input: RequestInfo | URL) => {
    const url = String(input);
    if (url.includes("/v1/draft-registrations/active")) {
      const d = opts.draft ?? "none";
      if (d === "none") {
        return Promise.resolve({ ok: true, status: 204, text: async () => "" } as Response);
      }
      return Promise.resolve({
        ok: true,
        status: 200,
        text: async () =>
          JSON.stringify({
            id: "draft-1",
            tenant_id: "tenant-1",
            owner_user_id: "user-1",
            draft_blob: d,
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

describe("DashboardPage axe pass", () => {
  test("admin-empty-state", async () => {
    mockFetch({ me: me([]) });
    const { container } = render(<DashboardPage />, { wrapper });
    await waitFor(() => screen.getByLabelText("admin-empty-state"));
    await expectNoAxeViolations(container);
  });

  test("portfolio hub with a your-court entry and a zero-use-case system", async () => {
    mockFetch({
      me: me(["system_owner"]),
      portfolio: [
        {
          system_id: "sys-1",
          system_name: "Acme Resume Screener",
          use_case_count: 1,
          highest_tier: "high_risk",
          use_cases: [
            {
              use_case_id: "uc-1",
              title: "Screen candidate applications",
              state: "intake",
              eu_tier: "high_risk",
              blocking: {
                state: "intake",
                verdict: "park",
                reason_code: "no_aiia",
                reason: "No assessment started for this use case",
                responsible_party: "user",
              },
            },
          ],
        },
      ],
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
    const { container } = render(<DashboardPage />, { wrapper });
    await waitFor(() => screen.getByLabelText("your-court"));
    await expectNoAxeViolations(container);
  });

  test("scaffolded-empty + draft-resume banner (FE-29)", async () => {
    mockFetch({
      me: me(["system_owner"]),
      portfolio: [],
      systems: [],
      draft: { catalogueProductName: "ATS Pro" },
    });
    const { container } = render(<DashboardPage />, { wrapper });
    await waitFor(() => screen.getByLabelText("draft-resume"));
    await expectNoAxeViolations(container);
  });

  test("populated portfolio + draft-resume banner (FE-29)", async () => {
    mockFetch({
      me: me(["system_owner"]),
      portfolio: [
        {
          system_id: "sys-1",
          system_name: "Acme Resume Screener",
          use_case_count: 1,
          highest_tier: "high_risk",
          use_cases: [
            {
              use_case_id: "uc-1",
              title: "Screen candidate applications",
              state: "intake",
              eu_tier: "high_risk",
              blocking: {
                state: "intake",
                verdict: "park",
                reason_code: "no_aiia",
                reason: "No assessment started for this use case",
                responsible_party: "user",
              },
            },
          ],
        },
      ],
      systems: [],
      draft: { catalogueProductName: "ATS Pro" },
    });
    const { container } = render(<DashboardPage />, { wrapper });
    await waitFor(() => screen.getByLabelText("draft-resume"));
    await expectNoAxeViolations(container);
  });
});
