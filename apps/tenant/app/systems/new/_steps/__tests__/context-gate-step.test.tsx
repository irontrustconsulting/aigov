/**
 * @jest-environment jsdom
 */
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { ContextGateStep } from "../context-gate-step";

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

const questionSet = {
  current_classification: null,
  residual_questions: {
    tree_version: "v1",
    questions: [
      {
        code: "Q1",
        text: "Does the system make autonomous decisions?",
        legal_ref: "Art. 6(2)",
        sort_order: 0,
        options: [
          { code: "yes", label: "Yes" },
          { code: "no", label: "No" },
        ],
      },
    ],
  },
};

function mockFetch({
  isSystemOwner,
  previewOutcome,
  submitOutcome,
}: {
  isSystemOwner: boolean;
  previewOutcome?: unknown;
  submitOutcome?: unknown;
}) {
  global.fetch = jest.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    const method = init?.method ?? "GET";

    if (url.includes("/v1/me")) {
      return Promise.resolve({
        ok: true,
        status: 200,
        text: async () =>
          JSON.stringify({
            membership_id: "m1",
            tenant_id: "t1",
            role: "member",
            email: null,
            name: null,
            governance_roles: isSystemOwner
              ? [{ id: "g1", key: "system_owner", name: "System Owner", description: null, line_of_defence: 1 }]
              : [],
          }),
      } as Response);
    }
    if (method === "GET" && url.includes("classification/context")) {
      return Promise.resolve({ ok: true, status: 200, text: async () => JSON.stringify(questionSet) } as Response);
    }
    if (method === "POST" && url.includes("/preview")) {
      return Promise.resolve({ ok: true, status: 200, text: async () => JSON.stringify(previewOutcome) } as Response);
    }
    if (method === "POST" && url.includes("classification/context")) {
      return Promise.resolve({ ok: true, status: 200, text: async () => JSON.stringify(submitOutcome) } as Response);
    }
    return Promise.resolve({ ok: true, status: 200, text: async () => JSON.stringify([]) } as Response);
  }) as jest.Mock;
}

afterEach(() => jest.restoreAllMocks());

describe("ContextGateStep", () => {
  test("an UNRESOLVED preview re-prompts the missing question and issues no write", async () => {
    mockFetch({
      isSystemOwner: true,
      previewOutcome: { kind: "UNRESOLVED", tier: null, subcategory_code: null, rationale: "Need more info", missing: ["Q1"] },
    });
    const onResolved = jest.fn();
    const onProhibitedHalt = jest.fn();

    render(<ContextGateStep useCaseId="uc-1" onResolved={onResolved} onProhibitedHalt={onProhibitedHalt} />, {
      wrapper,
    });

    await waitFor(() => screen.getByText(/does the system make autonomous/i));
    fireEvent.click(screen.getByRole("button", { name: /preview outcome/i }));

    await waitFor(() => expect(screen.getByText("This answer is still needed.")).toBeInTheDocument());
    expect(screen.queryByRole("button", { name: /^submit$/i })).not.toBeInTheDocument();
    expect(onResolved).not.toHaveBeenCalled();
    expect(onProhibitedHalt).not.toHaveBeenCalled();

    const fetchMock = global.fetch as jest.Mock;
    expect(fetchMock.mock.calls.some(([, init]) => String((init as RequestInit)?.method) === "POST" && true)).toBe(true);
    // The only POST so far must be the preview, never the submit endpoint without /preview.
    const posts = fetchMock.mock.calls.filter(([, init]) => (init as RequestInit | undefined)?.method === "POST");
    expect(posts.every(([url]) => String(url).includes("/preview"))).toBe(true);
  });

  test("a RESOLVED preview then submit calls onResolved (routes whose-court to reviewer)", async () => {
    mockFetch({
      isSystemOwner: true,
      previewOutcome: { kind: "RESOLVED", tier: "high_risk", subcategory_code: "SUB-1", rationale: "Resolved", missing: [] },
      submitOutcome: {
        outcome: { kind: "RESOLVED", tier: "high_risk", subcategory_code: "SUB-1", rationale: "Resolved", missing: [] },
        classification: {
          id: "c1", use_case_id: "uc-1", tier: "high_risk", status: "pending_review",
          overridden: false, proposed_tier: null, basis_subcategory_code: "SUB-1",
          basis_legal_ref: null, rationale: "Resolved", version: 1, is_current: true,
          created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z",
        },
      },
    });
    const onResolved = jest.fn();
    const onProhibitedHalt = jest.fn();

    render(<ContextGateStep useCaseId="uc-1" onResolved={onResolved} onProhibitedHalt={onProhibitedHalt} />, {
      wrapper,
    });

    await waitFor(() => screen.getByText(/does the system make autonomous/i));
    fireEvent.click(screen.getByRole("button", { name: /preview outcome/i }));

    await waitFor(() => screen.getByRole("button", { name: /^submit$/i }));
    fireEvent.click(screen.getByRole("button", { name: /^submit$/i }));

    await waitFor(() => expect(onResolved).toHaveBeenCalled());
    expect(onProhibitedHalt).not.toHaveBeenCalled();
  });

  test("a PROHIBITED_HALT submit calls onProhibitedHalt, not onResolved", async () => {
    mockFetch({
      isSystemOwner: true,
      previewOutcome: { kind: "PROHIBITED_HALT", tier: "prohibited", subcategory_code: null, rationale: "Prohibited practice", missing: [] },
      submitOutcome: {
        outcome: { kind: "PROHIBITED_HALT", tier: "prohibited", subcategory_code: null, rationale: "Prohibited practice", missing: [] },
        classification: null,
      },
    });
    const onResolved = jest.fn();
    const onProhibitedHalt = jest.fn();

    render(<ContextGateStep useCaseId="uc-1" onResolved={onResolved} onProhibitedHalt={onProhibitedHalt} />, {
      wrapper,
    });

    await waitFor(() => screen.getByText(/does the system make autonomous/i));
    fireEvent.click(screen.getByRole("button", { name: /preview outcome/i }));
    await waitFor(() => screen.getByRole("button", { name: /^submit$/i }));
    fireEvent.click(screen.getByRole("button", { name: /^submit$/i }));

    await waitFor(() => expect(onProhibitedHalt).toHaveBeenCalled());
    expect(onResolved).not.toHaveBeenCalled();
  });

  test("a bare contributor never sees the override control", async () => {
    mockFetch({
      isSystemOwner: false,
      previewOutcome: { kind: "RESOLVED", tier: "high_risk", subcategory_code: "SUB-1", rationale: "Resolved", missing: [] },
    });

    render(<ContextGateStep useCaseId="uc-1" onResolved={jest.fn()} onProhibitedHalt={jest.fn()} />, {
      wrapper,
    });

    await waitFor(() => screen.getByText(/does the system make autonomous/i));
    fireEvent.click(screen.getByRole("button", { name: /preview outcome/i }));

    await waitFor(() => screen.getByRole("button", { name: /^submit$/i }));
    expect(screen.queryByLabelText("Override tier")).not.toBeInTheDocument();
  });
});
