/**
 * @jest-environment jsdom
 *
 * F4 visual done-checks (UI-V1-TENANT-SKIN):
 * - Compact TierBadge rendered per queue row (not raw tier string)
 * - QueueRow density="compact" wraps each entry
 * - tier channel never carries a classification_status value
 */
import { render, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { ReviewQueueClient } from "../review-queue-client";

jest.mock("next/navigation", () => ({
  useRouter: () => ({ push: jest.fn() }),
}));

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

const QUEUE_ENTRIES = [
  {
    assessment_id: "a-1",
    use_case_id: "uc-1",
    tier_snapshot: "high_risk",
    submitted_by_name: "Ada Lovelace",
    submitted_by_email: "ada@example.com",
    submitted_at: "2024-03-01T10:00:00Z",
  },
  {
    assessment_id: "a-2",
    use_case_id: "uc-2",
    tier_snapshot: "limited_risk",
    submitted_by_name: null,
    submitted_by_email: null,
    submitted_at: null,
  },
];

function mockFetch(entries = QUEUE_ENTRIES) {
  global.fetch = jest.fn((input: RequestInfo | URL) => {
    const url = String(input);
    if (url.includes("/v1/me")) {
      return Promise.resolve({
        ok: true, status: 200,
        text: async () => JSON.stringify({
          membership_id: "m1", tenant_id: "t1", user_id: "u1",
          governance_roles: [{ key: "reviewer", display_name: "Reviewer" }],
        }),
        headers: new Headers({ "content-type": "application/json" }),
      } as Response);
    }
    if (url.includes("/v1/assessments/review-queue")) {
      return Promise.resolve({
        ok: true, status: 200,
        text: async () => JSON.stringify(entries),
        headers: new Headers({ "content-type": "application/json" }),
      } as Response);
    }
    return Promise.reject(new Error(`Unexpected fetch: ${url}`));
  });
}

afterEach(() => { jest.restoreAllMocks(); });

describe("F4 ReviewQueueClient — compact TierBadge per row", () => {
  test("each entry renders a compact TierBadge (no raw aria-label='tier' span)", async () => {
    mockFetch();
    const { container } = render(<ReviewQueueClient />, { wrapper });
    await waitFor(() => {
      expect(container.querySelector("[data-variant='compact'][data-tier='high']")).not.toBeNull();
    });
    expect(container.querySelector("[data-variant='compact'][data-tier='limited']")).not.toBeNull();
    // No raw tier span from the old implementation
    expect(container.querySelector("[aria-label='tier']")).toBeNull();
  });

  test("tier channel attribute is 'tier' for magnitude members (not verdict)", async () => {
    mockFetch();
    const { container } = render(<ReviewQueueClient />, { wrapper });
    await waitFor(() => {
      expect(container.querySelector("[data-tier-channel='tier']")).not.toBeNull();
    });
    const badges = container.querySelectorAll("[data-tier-channel='tier']");
    expect(badges.length).toBe(2);
  });

  test("data-tier never equals a classification_status value", async () => {
    mockFetch();
    const { container } = render(<ReviewQueueClient />, { wrapper });
    await waitFor(() => {
      expect(container.querySelector("[data-variant='compact']")).not.toBeNull();
    });
    const classificationValues = ["pending_review", "confirmed", "overridden"];
    for (const val of classificationValues) {
      expect(container.querySelector(`[data-tier='${val}']`)).toBeNull();
    }
  });

  test("non-reviewer sees access-denied message, no queue call", async () => {
    global.fetch = jest.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/v1/me")) {
        return Promise.resolve({
          ok: true, status: 200,
          text: async () => JSON.stringify({
            membership_id: "m1", tenant_id: "t1", user_id: "u1",
            governance_roles: [{ key: "system_owner", display_name: "System Owner" }],
          }),
          headers: new Headers({ "content-type": "application/json" }),
        } as Response);
      }
      return Promise.reject(new Error(`Unexpected fetch: ${url}`));
    });
    const { container } = render(<ReviewQueueClient />, { wrapper });
    await waitFor(() => {
      expect(container.textContent).toContain("reviewer access to this queue");
    });
    const calls = (global.fetch as jest.Mock).mock.calls.map(([u]: [RequestInfo | URL]) => String(u));
    expect(calls.some((u) => u.includes("review-queue"))).toBe(false);
  });
});
