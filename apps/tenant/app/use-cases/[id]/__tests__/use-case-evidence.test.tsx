/**
 * @jest-environment jsdom
 *
 * UI-F5-EVIDENCE WI-E — EvidenceManifest on the AIIA work surface.
 *
 * AI_SUGGESTED disposition gate: link button disabled-with-reason (INV-20, DF5-5).
 * Reviewer / canWrite=false: manifest chips rendered; no link / unlink controls (FE-8).
 * Write role: link fires POST /evidence-links with no If-Match header (DF5-4).
 * Unlink URL ends with /{evidenceId} — not a link-row id (DF5-9).
 * Cache isolation: link/unlink invalidate AIIA-detail only; no /lifecycle call (DF5-10, D-29).
 */
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import type { AssessmentItemRead, EvidenceListResponse } from "@irontrust/api-client";
import { EvidenceManifest } from "../_regions/evidence-manifest";

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

function makeItem(overrides: Partial<AssessmentItemRead> = {}): AssessmentItemRead {
  return {
    id: "item-1",
    assessment_id: "ass-1",
    section_key: "sec-A",
    risk_id: null,
    prompt: "Describe the risk",
    response: null,
    likelihood: null,
    severity: null,
    residual_likelihood: null,
    residual_severity: null,
    mitigation_plan: null,
    treatment_decision: null,
    treatment_rationale: null,
    provenance: "manual",
    selection_basis: null,
    source_ref: null,
    lock_version: 1,
    created_at: "2026-06-01T00:00:00Z",
    updated_at: "2026-06-01T00:00:00Z",
    source_assessment_id: null,
    source_type: null,
    control_links: [],
    evidence_links: [],
    ...overrides,
  };
}

const evidenceList: EvidenceListResponse = {
  items: [
    {
      id: "ev-1",
      title: "Risk assessment report",
      content_type: "application/pdf",
      size_bytes: 102400,
      sha256: "abc123def456abc123def456abc123def456abc123def456abc123def456abc1",
      uploaded_by_user_id: "user-1",
      created_at: "2026-06-01T10:00:00Z",
      updated_at: "2026-06-01T10:00:00Z",
      link_count: 0,
    },
  ],
  next_cursor: null,
};

const linkedItem: AssessmentItemRead = makeItem({
  evidence_links: [
    {
      evidence_id: "ev-1",
      title: "Risk assessment report",
      sha256: "abc123def456abc123def456abc123def456abc123def456abc123def456abc1",
      content_type: "application/pdf",
      size_bytes: 102400,
    },
  ],
});

function mockFetch(list: EvidenceListResponse = evidenceList) {
  global.fetch = jest.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    const method = init?.method ?? "GET";
    let body: unknown = {};
    if (url.includes("/v1/evidence") && method === "GET") body = list;
    return Promise.resolve({
      ok: true,
      status: method === "DELETE" ? 204 : 200,
      text: async () => (method === "DELETE" ? "" : JSON.stringify(body)),
    } as Response);
  }) as jest.Mock;
}

function fetchedCalls() {
  return (global.fetch as jest.Mock).mock.calls as [RequestInfo | URL, RequestInit?][];
}

afterEach(() => jest.restoreAllMocks());

describe("EvidenceManifest (UI-F5-EVIDENCE WI-E)", () => {
  test("AI_SUGGESTED item: link button disabled-with-reason; reason note shown", async () => {
    mockFetch();

    const item = makeItem({ provenance: "ai_suggested" });

    render(
      <EvidenceManifest item={item} assessmentId="ass-1" canWrite={true} />,
      { wrapper }
    );

    const linkBtn = await screen.findByRole("button", { name: /link evidence/i });
    expect(linkBtn).toBeDisabled();

    expect(
      screen.getByRole("note")
    ).toHaveTextContent(/confirm or amend this item before linking evidence/i);
  });

  test("non-AI_SUGGESTED item: link button enabled; clicking opens picker", async () => {
    mockFetch();

    render(
      <EvidenceManifest item={makeItem()} assessmentId="ass-1" canWrite={true} />,
      { wrapper }
    );

    const linkBtn = await screen.findByRole("button", { name: /link evidence/i });
    expect(linkBtn).not.toBeDisabled();

    fireEvent.click(linkBtn);

    // Dialog opens with evidence item title
    await waitFor(() =>
      expect(screen.getByText("Risk assessment report")).toBeInTheDocument()
    );
  });

  test("link: fires POST to /evidence-links with no If-Match header", async () => {
    mockFetch();

    render(
      <EvidenceManifest item={makeItem()} assessmentId="ass-1" canWrite={true} />,
      { wrapper }
    );

    // Open the picker
    const linkBtn = await screen.findByRole("button", { name: /link evidence/i });
    fireEvent.click(linkBtn);

    // Select the first evidence item
    const itemBtn = await screen.findByRole("option", { name: /risk assessment report/i });
    fireEvent.click(itemBtn);

    await waitFor(() => {
      const linkCalls = fetchedCalls().filter(([url]) =>
        String(url).includes("evidence-links") && !String(url).match(/evidence-links\//)
      );
      expect(linkCalls.length).toBeGreaterThan(0);
    });

    const [url, init] = fetchedCalls().find(([url]) =>
      String(url).includes("evidence-links") && !String(url).match(/evidence-links\//)
    )!;

    expect(String(url)).toContain("/items/item-1/evidence-links");
    expect(init?.method).toBe("POST");
    expect((init?.headers as Record<string, string>)?.["If-Match"]).toBeUndefined();

    const bodyJson = JSON.parse(init?.body as string);
    expect(bodyJson.evidence_id).toBe("ev-1");
  });

  test("link/unlink: no /lifecycle URL called (cache isolation, DF5-10)", async () => {
    mockFetch();

    render(
      <EvidenceManifest item={linkedItem} assessmentId="ass-1" canWrite={true} />,
      { wrapper }
    );

    const unlinkBtn = await screen.findByRole("button", { name: /unlink risk assessment report/i });
    fireEvent.click(unlinkBtn);

    await waitFor(() => {
      const calls = fetchedCalls().filter(([, init]) => (init?.method ?? "GET") === "DELETE");
      expect(calls.length).toBeGreaterThan(0);
    });

    const lifecycleCalls = fetchedCalls().filter(([url]) => String(url).includes("/lifecycle"));
    expect(lifecycleCalls).toHaveLength(0);
  });

  test("unlink URL ends with /{evidenceId} (DF5-9)", async () => {
    mockFetch();

    render(
      <EvidenceManifest item={linkedItem} assessmentId="ass-1" canWrite={true} />,
      { wrapper }
    );

    const unlinkBtn = await screen.findByRole("button", { name: /unlink risk assessment report/i });
    fireEvent.click(unlinkBtn);

    await waitFor(() => {
      const deleteCalls = fetchedCalls().filter(([, init]) => (init?.method ?? "GET") === "DELETE");
      expect(deleteCalls.length).toBeGreaterThan(0);
    });

    const [deleteUrl] = fetchedCalls().find(([, init]) => (init?.method ?? "GET") === "DELETE")!;
    // Must end with the evidence_id, not a link-row id
    expect(String(deleteUrl)).toMatch(/\/evidence-links\/ev-1$/);
  });

  test("canWrite=false (reviewer): chips shown without unlink; no link button", async () => {
    mockFetch();

    render(
      <EvidenceManifest item={linkedItem} assessmentId="ass-1" canWrite={false} />,
      { wrapper }
    );

    await waitFor(() =>
      expect(screen.getByText("Risk assessment report")).toBeInTheDocument()
    );

    // No unlink button
    expect(screen.queryByRole("button", { name: /unlink/i })).not.toBeInTheDocument();
    // No link button
    expect(screen.queryByRole("button", { name: /link evidence/i })).not.toBeInTheDocument();
  });

  test("item with no evidence links and canWrite=false: empty manifest, no controls", async () => {
    mockFetch();

    render(
      <EvidenceManifest item={makeItem()} assessmentId="ass-1" canWrite={false} />,
      { wrapper }
    );

    // Await fetch to settle (evidence list still requested)
    await waitFor(() =>
      expect(
        screen.queryByRole("list", { name: /linked-evidence/i })
      ).not.toBeInTheDocument()
    );

    expect(screen.queryByRole("button", { name: /link evidence/i })).not.toBeInTheDocument();
  });
});
