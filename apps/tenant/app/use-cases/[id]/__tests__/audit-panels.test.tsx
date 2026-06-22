/**
 * @jest-environment jsdom
 *
 * UI-F6-AUDITPACK WI-5 — per-use-case audit panels assertions.
 * Coverage panel hidden when AIIA not APPROVED; shown when APPROVED (INV-38/DF3-2).
 * ATO document: fires only on button click; 404 → "never authorised" empty-state.
 * ?round=N deep-link: passed to useAtoDocument.
 * Export: fires only on click; no re-fetch on window focus (INV-53).
 * No round enumeration call — only the ATO doc itself.
 */

// Mock useSearchParams so tests can control ?round=N
jest.mock("next/navigation", () => ({
  useSearchParams: jest.fn(() => new URLSearchParams()),
}));

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import type { CoverageMatrixRead, AtoDocumentRead, UseCaseExportRead } from "@irontrust/api-client";
import { useSearchParams } from "next/navigation";
import { AuditPanels } from "../_regions/audit-panels";

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

const matrix: CoverageMatrixRead = {
  scope: "assessment",
  scope_id: "ass-1",
  framework_filter: null,
  include_unapproved: false,
  controls: [{ control_id: "c1", code: "ISO-5.1", title: "Governance", verdict: "SATISFIED", breakdown: { satisfied: 1, partial: 0, open: 0, downgraded_unsubstantiated: 0, contributing_refs: [] }, framework_mappings: [] }],
  frameworks: [],
  unaddressed_controls: [],
  not_an_obligation_set: false,
  generated_at: "2026-06-22T12:00:00Z",
};

const atoDoc: AtoDocumentRead = {
  ato: {
    id: "ato-1",
    use_case_id: "uc-1",
    assessment_id: "ass-1",
    submission_round: 1,
    tier: "high_risk",
    assessment_version: 1,
    authorised_by_name: "Alice Auth",
    authorised_by_email: "alice@acme.test",
    authorised_at: "2026-05-01T10:00:00Z",
    residual_risk_statement: "Risk accepted with mitigations.",
    live_state: "authorised",
  },
  current_assessment_summary: {
    id: "ass-1",
    use_case_id: "uc-1",
    type: "aiia",
    parent_aiia_id: null,
    status: "approved",
    version: 1,
    tier_snapshot: "high_risk",
    classification_version: 1,
    is_current: true,
    lock_version: 1,
    submission_round: 1,
    submitted_at: "2026-04-15T10:00:00Z",
    created_at: "2026-04-01T10:00:00Z",
    updated_at: "2026-05-01T10:00:00Z",
  },
  current_classification_summary: null,
  basis_is_current_state_not_authorisation_snapshot: true,
};

const exportPack: Partial<UseCaseExportRead> = {
  use_case_id: "uc-1",
  system: { id: "sys-1", name: "Test System", is_custom: true, catalogue_product: null, catalogue_vendor: null, owner_user_id: null, operator_role: null, hosting_model: null, usage_context: null, human_oversight_type: null, lifecycle_stage: null, data_categories: [], affected_parties: [], purpose: null, use_case_count: 1, use_case_lifecycle_states: [], created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z" },
  classification_history: [],
  assessment: { aiia_id: "ass-1", status: "approved", native_items: [], feeders: [] },
  evidence_manifest: [],
  coverage: matrix,
  lifecycle_trail: [],
  atos: [],
  audit_trail: [],
  generated_at: "2026-06-22T12:00:00Z",
  content_hash: "abc123",
};

function mockFetch(overrides: { coverage?: unknown; atoStatus?: number; atoBody?: unknown; exportBody?: unknown } = {}) {
  global.fetch = jest.fn((input: RequestInfo | URL) => {
    const url = String(input);
    if (url.includes("/v1/assessments/ass-1/coverage")) {
      return Promise.resolve({ ok: true, status: 200, text: async () => JSON.stringify(overrides.coverage ?? matrix) } as Response);
    }
    if (url.includes("/authorisation/document")) {
      const status = overrides.atoStatus ?? 200;
      return Promise.resolve({ ok: status < 400, status, text: async () => JSON.stringify(overrides.atoBody ?? atoDoc) } as Response);
    }
    if (url.includes("/export")) {
      return Promise.resolve({ ok: true, status: 200, text: async () => JSON.stringify(overrides.exportBody ?? exportPack) } as Response);
    }
    if (url.includes("/v1/evidence/")) {
      return Promise.resolve({ ok: true, status: 200, text: async () => JSON.stringify({ id: "ev-1", download_url: "https://s3.test/ev-1" }) } as Response);
    }
    return Promise.resolve({ ok: true, status: 200, text: async () => JSON.stringify({}) } as Response);
  }) as jest.Mock;
}

function fetchedUrls(): string[] {
  return (global.fetch as jest.Mock).mock.calls.map(([url]: [RequestInfo | URL]) => String(url));
}

beforeEach(() => {
  (useSearchParams as jest.Mock).mockReturnValue(new URLSearchParams());
  Object.defineProperty(window, "location", { value: { href: "" }, writable: true, configurable: true });
});

afterEach(() => jest.restoreAllMocks());

describe("AuditPanels (UI-F6-AUDITPACK WI-5)", () => {
  test("canView=false: renders nothing", async () => {
    mockFetch();
    const { container } = render(
      <AuditPanels useCaseId="uc-1" assessmentId="ass-1" assessmentStatus="approved" canView={false} />,
      { wrapper }
    );
    expect(container.firstChild).toBeNull();
  });

  test("coverage hidden when AIIA not APPROVED; no coverage fetch issued", async () => {
    mockFetch();
    render(
      <AuditPanels useCaseId="uc-1" assessmentId="ass-1" assessmentStatus="draft" canView={true} />,
      { wrapper }
    );
    await waitFor(() =>
      expect(screen.getByText(/coverage available after aiia approval/i)).toBeInTheDocument()
    );
    expect(fetchedUrls().filter((u) => u.includes("/coverage"))).toHaveLength(0);
  });

  test("coverage shown when AIIA is APPROVED", async () => {
    mockFetch();
    render(
      <AuditPanels useCaseId="uc-1" assessmentId="ass-1" assessmentStatus="approved" canView={true} />,
      { wrapper }
    );
    await waitFor(() =>
      expect(screen.getByRole("region", { name: /use-case-coverage/i })).toBeInTheDocument()
    );
    expect(fetchedUrls().filter((u) => u.includes("/assessments/ass-1/coverage"))).toHaveLength(1);
  });

  test("ATO document: fires only on button click; not on mount", async () => {
    mockFetch();
    render(
      <AuditPanels useCaseId="uc-1" assessmentId="ass-1" assessmentStatus="approved" canView={true} />,
      { wrapper }
    );
    await waitFor(() =>
      expect(screen.getByRole("region", { name: /ato-document-section/i })).toBeInTheDocument()
    );
    // Not fired yet
    expect(fetchedUrls().filter((u) => u.includes("/authorisation/document"))).toHaveLength(0);

    fireEvent.click(screen.getByRole("button", { name: /view ato document/i }));

    await waitFor(() =>
      expect(fetchedUrls().filter((u) => u.includes("/authorisation/document"))).toHaveLength(1)
    );
    // Drift caveat always shown (DF6-5)
    await waitFor(() =>
      expect(screen.getByRole("note", { name: /ato-drift-caveat/i })).toBeInTheDocument()
    );
  });

  test("ATO document 404: renders never-authorised empty-state", async () => {
    mockFetch({ atoStatus: 404, atoBody: { detail: "Not found" } });
    render(
      <AuditPanels useCaseId="uc-1" assessmentId="ass-1" assessmentStatus="approved" canView={true} />,
      { wrapper }
    );
    fireEvent.click(await screen.findByRole("button", { name: /view ato document/i }));
    await waitFor(() =>
      expect(screen.getByText(/this use case has never been authorised/i)).toBeInTheDocument()
    );
    // No enumeration call (DF6-10)
    expect(fetchedUrls().filter((u) => u.includes("/authorisation") && !u.includes("/document"))).toHaveLength(0);
  });

  test("export fires only on button click; no re-fetch on window focus (INV-53)", async () => {
    mockFetch();
    render(
      <AuditPanels useCaseId="uc-1" assessmentId="ass-1" assessmentStatus="approved" canView={true} />,
      { wrapper }
    );
    await waitFor(() =>
      expect(screen.getByRole("region", { name: /use-case-export/i })).toBeInTheDocument()
    );
    expect(fetchedUrls().filter((u) => u.includes("/export"))).toHaveLength(0);

    fireEvent.click(screen.getByRole("button", { name: /generate use-case audit pack/i }));

    await waitFor(() =>
      expect(fetchedUrls().filter((u) => u.includes("/use-cases/uc-1/export"))).toHaveLength(1)
    );

    // window focus must not trigger another export call
    window.dispatchEvent(new Event("focus"));
    await new Promise((r) => setTimeout(r, 50));
    expect(fetchedUrls().filter((u) => u.includes("/use-cases/uc-1/export"))).toHaveLength(1);
  });

  test("?round=2 deep-link: useAtoDocument called with round=2 in URL", async () => {
    (useSearchParams as jest.Mock).mockReturnValue(new URLSearchParams("round=2"));
    mockFetch();
    render(
      <AuditPanels useCaseId="uc-1" assessmentId="ass-1" assessmentStatus="approved" canView={true} />,
      { wrapper }
    );
    fireEvent.click(await screen.findByRole("button", { name: /view ato document/i }));
    await waitFor(() => {
      const urls = fetchedUrls();
      expect(urls.some((u) => u.includes("/authorisation/document") && u.includes("round=2"))).toBe(true);
    });
  });
});
