/**
 * @jest-environment jsdom
 *
 * UI-F5-EVIDENCE WI-D — Evidence repository home role-gate assertions.
 * Admin (zero gov roles): empty-state; no /v1/evidence request issued (DF5-7).
 * Reviewer: list shown; upload / delete controls absent (FE-8).
 * system_owner: list + upload shown; delete disabled-with-reason when link_count > 0 (INV-19).
 * Download: on-intent only — one GET /evidence/{id} per click, no per-row prefetch (DF5-3).
 */
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import type { MeRead, EvidenceListResponse, EvidenceDetailRead } from "@irontrust/api-client";
import { EvidenceHomeClient } from "../evidence-home-client";

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

const listWithLinked: EvidenceListResponse = {
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
      link_count: 2,
    },
  ],
  next_cursor: null,
};

const listWithUnlinked: EvidenceListResponse = {
  items: [{ ...listWithLinked.items[0], link_count: 0 }],
  next_cursor: null,
};

const evidenceDetail: EvidenceDetailRead = {
  ...listWithLinked.items[0],
  download_url: "https://s3.example.test/evidence/ev-1?sig=abc",
};

function mockFetch(meBody: MeRead, list: EvidenceListResponse = listWithLinked) {
  global.fetch = jest.fn((input: RequestInfo | URL) => {
    const url = String(input);
    let body: unknown;
    if (url.includes("/v1/me")) {
      body = meBody;
    } else if (url.match(/\/v1\/evidence\/[^?]+/)) {
      // Detail endpoint: GET /v1/evidence/{id}
      body = evidenceDetail;
    } else if (url.includes("/v1/evidence")) {
      // List endpoint: GET /v1/evidence?limit=50
      body = list;
    } else {
      body = {};
    }
    return Promise.resolve({
      ok: true,
      status: 200,
      text: async () => JSON.stringify(body),
    } as Response);
  }) as jest.Mock;
}

function fetchedUrls(): string[] {
  return (global.fetch as jest.Mock).mock.calls.map(([url]: [RequestInfo | URL]) => String(url));
}

beforeEach(() => {
  Object.defineProperty(window, "location", {
    value: { href: "" },
    writable: true,
    configurable: true,
  });
});

afterEach(() => jest.restoreAllMocks());

describe("EvidenceHomeClient (UI-F5-EVIDENCE WI-D)", () => {
  test("admin: empty-state rendered; no /v1/evidence request issued", async () => {
    mockFetch(me([]));

    render(<EvidenceHomeClient />, { wrapper });

    await waitFor(() =>
      expect(
        screen.getByText(/evidence is not available for your current role/i)
      ).toBeInTheDocument()
    );

    const evidenceCalls = fetchedUrls().filter((u) => u.includes("/v1/evidence"));
    expect(evidenceCalls).toHaveLength(0);
  });

  test("reviewer: list shown; upload section and delete controls absent", async () => {
    mockFetch(me(["reviewer"]), listWithLinked);

    render(<EvidenceHomeClient />, { wrapper });

    await waitFor(() =>
      expect(screen.getByText("Risk assessment report")).toBeInTheDocument()
    );

    // No upload section
    expect(screen.queryByRole("region", { name: /upload-evidence/i })).not.toBeInTheDocument();
    // No delete button (onDelete undefined → EvidenceTable omits SodAction)
    expect(screen.queryByRole("button", { name: /delete/i })).not.toBeInTheDocument();
    // Download is present (all gov roles)
    expect(screen.getByRole("button", { name: /download/i })).toBeInTheDocument();
  });

  test("system_owner: list + upload shown; delete disabled-with-reason when link_count > 0", async () => {
    mockFetch(me(["system_owner"]), listWithLinked);

    render(<EvidenceHomeClient />, { wrapper });

    await waitFor(() =>
      expect(screen.getByText("Risk assessment report")).toBeInTheDocument()
    );

    // Upload section present
    expect(screen.getByRole("region", { name: /upload-evidence/i })).toBeInTheDocument();

    // Delete button rendered but disabled (link_count: 2 > 0)
    const deleteBtn = screen.getByRole("button", { name: /delete/i });
    expect(deleteBtn).toBeDisabled();
    expect(screen.getByRole("note")).toHaveTextContent(/cannot delete.*linked/i);
  });

  test("system_owner: delete enabled when link_count is 0", async () => {
    mockFetch(me(["system_owner"]), listWithUnlinked);

    render(<EvidenceHomeClient />, { wrapper });

    await waitFor(() =>
      expect(screen.getByText("Risk assessment report")).toBeInTheDocument()
    );

    const deleteBtn = screen.getByRole("button", { name: /delete/i });
    expect(deleteBtn).not.toBeDisabled();
  });

  test("download: fires one GET /evidence/{id} on click; no per-row prefetch at render", async () => {
    mockFetch(me(["reviewer"]), listWithLinked);

    render(<EvidenceHomeClient />, { wrapper });

    await waitFor(() =>
      expect(screen.getByText("Risk assessment report")).toBeInTheDocument()
    );

    // No detail calls yet — list rendered with no prefetch (DF5-3)
    const callsBeforeClick = fetchedUrls().filter((u) => u.match(/\/v1\/evidence\/[^?]+/));
    expect(callsBeforeClick).toHaveLength(0);

    fireEvent.click(screen.getByRole("button", { name: /download/i }));

    await waitFor(() =>
      expect(window.location.href).toBe(evidenceDetail.download_url)
    );

    // Exactly one detail call was fired
    const detailCalls = fetchedUrls().filter((u) => u.match(/\/v1\/evidence\/[^?]+/));
    expect(detailCalls).toHaveLength(1);
    expect(detailCalls[0]).toContain("ev-1");
  });
});
