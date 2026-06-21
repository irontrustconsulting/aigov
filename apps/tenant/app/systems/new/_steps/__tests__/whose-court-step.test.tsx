/**
 * @jest-environment jsdom
 */
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { WhoseCourtStep } from "../whose-court-step";

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

function mockLifecycle(blocking: unknown) {
  global.fetch = jest.fn().mockResolvedValue({
    ok: true,
    status: 200,
    text: async () =>
      JSON.stringify({
        use_case_id: "uc-1",
        state: "intake",
        held_from_state: null,
        held_reason: null,
        gates: [],
        blocking,
      }),
  } as Response) as jest.Mock;
}

afterEach(() => jest.restoreAllMocks());

describe("WhoseCourtStep", () => {
  test("a catalogue-linked, unapproved use case shows it's with the authoriser (vendor/product clearance)", async () => {
    mockLifecycle({
      state: "vendor_check",
      verdict: "park",
      reason_code: "vendor_not_started",
      reason: "Vendor clearance not yet requested",
      responsible_party: "authoriser",
    });

    render(<WhoseCourtStep useCaseId="uc-1" />, { wrapper });

    await waitFor(() => expect(screen.getByText(/with the authoriser/i)).toBeInTheDocument());
    expect(screen.getByText(/vendor\/product clearance/i)).toBeInTheDocument();
  });

  test("a bridge-resolved, no-vendor-link use case shows it's with you (start the assessment)", async () => {
    mockLifecycle({
      state: "intake",
      verdict: "park",
      reason_code: "no_aiia",
      reason: "No assessment started for this use case",
      responsible_party: "user",
    });

    render(<WhoseCourtStep useCaseId="uc-1" />, { wrapper });

    await waitFor(() => expect(screen.getByText(/with you/i)).toBeInTheDocument());
    expect(screen.getByText(/start the assessment/i)).toBeInTheDocument();
  });

  test("a context-path PENDING_REVIEW use case shows it's with the reviewer", async () => {
    mockLifecycle({
      state: "intake",
      verdict: "park",
      reason_code: "tier_not_ratified",
      reason: "Classification tier not yet ratified (eu_tier pending)",
      responsible_party: "reviewer",
    });

    render(<WhoseCourtStep useCaseId="uc-1" />, { wrapper });

    await waitFor(() => expect(screen.getByText(/with the reviewer/i)).toBeInTheDocument());
    expect(screen.getByText(/pending review/i)).toBeInTheDocument();
  });

  test("no blocking gate renders a neutral on-track message, not an error", async () => {
    mockLifecycle(null);

    render(<WhoseCourtStep useCaseId="uc-1" />, { wrapper });

    await waitFor(() =>
      expect(screen.getByText(/nothing is blocking/i)).toBeInTheDocument()
    );
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });
});
