/**
 * @jest-environment jsdom
 *
 * UI-F6-AUDITPACK WI-3 — /audit programme home role-gate assertions.
 * Admin (zero gov roles): empty-state; no coverage/export call (DF2-5).
 * Any gov role: tenant coverage matrix rendered; framework export button present.
 * Framework export: fires only after button click; no re-fire on window focus.
 * not_an_obligation_set: banner present when true.
 * include_unapproved toggle: AuditGradeDivider label appears when toggled on.
 */
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import type { MeRead, CoverageMatrixRead } from "@irontrust/api-client";
import { AuditHomeClient } from "../audit-home-client";

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

const matrix: CoverageMatrixRead = {
  scope: "tenant",
  scope_id: null,
  framework_filter: null,
  include_unapproved: false,
  controls: [
    {
      control_id: "ctrl-1",
      code: "ISO-5.1",
      title: "Governance",
      verdict: "SATISFIED",
      breakdown: { satisfied: 1, partial: 0, open: 0, downgraded_unsubstantiated: 0, contributing_refs: [] },
      framework_mappings: [],
    },
  ],
  frameworks: [],
  unaddressed_controls: [],
  not_an_obligation_set: false,
  generated_at: "2026-06-22T12:00:00Z",
};

const matrixWithBanner: CoverageMatrixRead = {
  ...matrix,
  not_an_obligation_set: true,
  unaddressed_controls: [
    { control_id: "ctrl-2", code: "ISO-6.1", title: "Risk management", framework_mappings: [] },
  ],
};

function mockFetch(meBody: MeRead, coverageBody: CoverageMatrixRead = matrix) {
  global.fetch = jest.fn((input: RequestInfo | URL) => {
    const url = String(input);
    let body: unknown;
    if (url.includes("/v1/me")) body = meBody;
    else if (url.includes("/v1/export")) body = { framework: "ISO_42001", coverage: coverageBody, substantiation_manifest: [], generated_at: "2026-06-22T12:00:00Z", content_hash: "abc" };
    else if (url.includes("/v1/coverage")) body = coverageBody;
    else body = {};
    return Promise.resolve({ ok: true, status: 200, text: async () => JSON.stringify(body) } as Response);
  }) as jest.Mock;
}

function fetchedUrls(): string[] {
  return (global.fetch as jest.Mock).mock.calls.map(([url]: [RequestInfo | URL]) => String(url));
}

afterEach(() => jest.restoreAllMocks());

describe("AuditHomeClient (UI-F6-AUDITPACK)", () => {
  test("admin: empty-state rendered; no coverage or export request issued", async () => {
    mockFetch(me([]));
    render(<AuditHomeClient />, { wrapper });
    await waitFor(() =>
      expect(screen.getByText(/doesn't hold a governance role/i)).toBeInTheDocument()
    );
    const govCalls = fetchedUrls().filter((u) => u.includes("/v1/coverage") || u.includes("/v1/export"));
    expect(govCalls).toHaveLength(0);
  });

  test("any gov role: coverage matrix rendered after load", async () => {
    mockFetch(me(["auditor"]));
    render(<AuditHomeClient />, { wrapper });
    await waitFor(() =>
      expect(screen.getByRole("region", { name: /tenant-coverage/i })).toBeInTheDocument()
    );
    expect(fetchedUrls().filter((u) => u.includes("/v1/coverage"))).toHaveLength(1);
  });

  test("not_an_obligation_set: banner present when true", async () => {
    mockFetch(me(["auditor"]), matrixWithBanner);
    render(<AuditHomeClient />, { wrapper });
    await waitFor(() =>
      expect(screen.getByRole("note", { name: /not-an-obligation-set-banner/i })).toBeInTheDocument()
    );
  });

  test("framework export: not fired on mount; fires only after button click", async () => {
    mockFetch(me(["auditor"]));
    render(<AuditHomeClient />, { wrapper });
    await waitFor(() =>
      expect(screen.getByRole("region", { name: /tenant-coverage/i })).toBeInTheDocument()
    );

    // No export call on mount
    expect(fetchedUrls().filter((u) => u.includes("/v1/export"))).toHaveLength(0);

    // Select a framework then click generate
    const select = screen.getByRole("combobox", { name: /framework-select/i });
    fireEvent.change(select, { target: { value: "ISO_42001" } });

    const generateBtn = screen.getByRole("button", { name: /generate framework audit pack/i });
    fireEvent.click(generateBtn);

    await waitFor(() =>
      expect(fetchedUrls().filter((u) => u.includes("/v1/export"))).toHaveLength(1)
    );
  });

  test("include_unapproved toggle: AuditGradeDivider label appears when toggled on", async () => {
    mockFetch(me(["auditor"]));
    render(<AuditHomeClient />, { wrapper });
    await waitFor(() =>
      expect(screen.getByRole("region", { name: /tenant-coverage/i })).toBeInTheDocument()
    );

    // No divider initially
    expect(screen.queryByRole("region", { name: /audit-grade-divider/i })).not.toBeInTheDocument();

    const toggle = screen.getByRole("checkbox", { name: /include in-progress/i });
    fireEvent.click(toggle);

    await waitFor(() =>
      expect(screen.getByRole("region", { name: /audit-grade-divider/i })).toBeInTheDocument()
    );
  });
});
