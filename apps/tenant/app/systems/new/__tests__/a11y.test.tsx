/**
 * @jest-environment jsdom
 *
 * WI-11: axe pass on every wizard screen (WCAG 2.1 AA baseline, FRONTEND §4).
 * Each screen is rendered in its "settled" state (post-load) and checked
 * with jest-axe — the deterministic, CI-friendly half of the a11y bar; the
 * manual keyboard-only pass is the other half (see the sprint-closure notes
 * in STATE.md for what that pass covered and its limits in this session).
 */
import { render, waitFor, fireEvent } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import type { ClassificationRead } from "@irontrust/api-client";
import { expectNoAxeViolations } from "../../../../test-utils/axe";
import { DrillDownStep } from "../_steps/drill-down-step";
import { IntakeCaptureStep } from "../_steps/intake-capture-step";
import { PrefillStep } from "../_steps/prefill-step";
import { UseCaseCreateStep } from "../_steps/use-case-create-step";
import { ResolvedTierStep } from "../_steps/resolved-tier-step";
import { ContextGateStep } from "../_steps/context-gate-step";
import { TerminalProhibited } from "../_steps/terminal-prohibited";
import { WhoseCourtStep } from "../_steps/whose-court-step";
import { NeedsSystemOwner } from "../_steps/needs-system-owner";
import { AssuranceReadOnly } from "../_steps/assurance-readonly";

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

function jsonResponse(body: unknown) {
  return Promise.resolve({ ok: true, status: 200, text: async () => JSON.stringify(body) } as Response);
}

afterEach(() => jest.restoreAllMocks());

const classification: ClassificationRead = {
  id: "c1",
  use_case_id: "uc-1",
  tier: "high_risk",
  rationale: "Mapped via product category",
  version: 1,
  is_current: true,
  overridden: false,
  proposed_tier: null,
  basis_subcategory_code: "SUB-1",
  basis_legal_ref: "Art. 6(2)",
  requires_context: false,
};

describe("WI-11 axe pass — wizard screens", () => {
  test("DrillDownStep", async () => {
    // Empty taxonomy — mock returns [] for all product-category requests
    global.fetch = jest.fn(() => jsonResponse([])) as jest.Mock;
    const { container, getByText } = render(<DrillDownStep onComplete={jest.fn()} />, { wrapper });
    await waitFor(() => getByText(/no categories available/i));
    await expectNoAxeViolations(container);
  });

  test("IntakeCaptureStep", async () => {
    const fetchMock = jest.fn(() => jsonResponse([]));
    global.fetch = fetchMock as jest.Mock;
    const { container, getByLabelText } = render(
      <IntakeCaptureStep isCustom={false} catalogueProductId="p1" onSubmit={jest.fn()} />,
      { wrapper }
    );
    await waitFor(() => getByLabelText("System name"));
    // Six vocab-list reads fire on mount — let them all settle before the
    // axe pass, otherwise a late state update lands after the test returns.
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(6));
    await expectNoAxeViolations(container);
  });

  test("PrefillStep with facts", async () => {
    global.fetch = jest.fn(() =>
      jsonResponse({
        catalogue_product_id: "p1",
        facts: [
          {
            key: "hosting_region",
            value: { region: "EU" },
            source_url: null,
            source_label: "Vendor documentation",
            last_checked_at: null,
            provenance: "catalogue_curated",
          },
        ],
      })
    ) as jest.Mock;
    const { container, getByText } = render(<PrefillStep systemId="sys-1" onContinue={jest.fn()} />, {
      wrapper,
    });
    await waitFor(() => getByText("EU"));
    await expectNoAxeViolations(container);
  });

  test("UseCaseCreateStep", async () => {
    global.fetch = jest.fn(() => jsonResponse([])) as jest.Mock;
    const { container, getByLabelText } = render(
      <UseCaseCreateStep systemId="sys-1" onCreated={jest.fn()} />,
      { wrapper }
    );
    await waitFor(() => getByLabelText(/what are you using this for/i));
    await expectNoAxeViolations(container);
  });

  test("ResolvedTierStep with override panel open", async () => {
    global.fetch = jest.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/v1/me")) {
        return jsonResponse({
          membership_id: "m1", tenant_id: "t1", role: "member", email: null, name: null, tenant_name: "Acme Corp",
          governance_roles: [{ id: "g1", key: "system_owner", name: "System Owner", description: null, line_of_defence: 1 }],
        });
      }
      if (url.includes("eu-ai-act/subcategories")) {
        return jsonResponse([{ id: "s1", code: "HR-1", name: "High risk sub", description: null, category_id: "cat-1", tier: "high_risk" }]);
      }
      return jsonResponse([]);
    }) as jest.Mock;

    const { container, getByRole } = render(
      <ResolvedTierStep useCaseId="uc-1" classification={classification} onOverrideApplied={jest.fn()} onContinue={jest.fn()} />,
      { wrapper }
    );
    await waitFor(() => getByRole("button", { name: /override classification/i }));
    await expectNoAxeViolations(container);

    fireEvent.click(getByRole("button", { name: /override classification/i }));
    await waitFor(() => getByRole("button", { name: /confirm override/i }));
    await expectNoAxeViolations(container);
  });

  test("ContextGateStep", async () => {
    global.fetch = jest.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/v1/me")) {
        return jsonResponse({ membership_id: "m1", tenant_id: "t1", role: "member", email: null, name: null, tenant_name: "Acme Corp", governance_roles: [] });
      }
      if (url.includes("classification/context")) {
        return jsonResponse({
          current_classification: null,
          residual_questions: {
            tree_version: "v1",
            questions: [
              {
                code: "Q1",
                text: "Does the system make autonomous decisions?",
                legal_ref: "Art. 6(2)",
                sort_order: 0,
                options: [{ code: "yes", label: "Yes" }, { code: "no", label: "No" }],
              },
            ],
          },
        });
      }
      return jsonResponse([]);
    }) as jest.Mock;

    const { container, getByText } = render(
      <ContextGateStep useCaseId="uc-1" onResolved={jest.fn()} onProhibitedHalt={jest.fn()} />,
      { wrapper }
    );
    await waitFor(() => getByText(/does the system make autonomous/i));
    await expectNoAxeViolations(container);
  });

  test("TerminalProhibited", async () => {
    const { container } = render(<TerminalProhibited />);
    await expectNoAxeViolations(container);
  });

  test("WhoseCourtStep", async () => {
    global.fetch = jest.fn(() =>
      jsonResponse({
        use_case_id: "uc-1",
        state: "intake",
        held_from_state: null,
        held_reason: null,
        gates: [],
        blocking: {
          state: "vendor_check",
          verdict: "park",
          reason_code: "vendor_not_started",
          reason: "Vendor clearance not yet requested",
          responsible_party: "authoriser",
        },
      })
    ) as jest.Mock;
    const { container, getByText } = render(<WhoseCourtStep useCaseId="uc-1" />, { wrapper });
    await waitFor(() => getByText(/with the authoriser/i));
    await expectNoAxeViolations(container);
  });

  test("NeedsSystemOwner", async () => {
    const { container } = render(<NeedsSystemOwner />);
    await expectNoAxeViolations(container);
  });

  test("AssuranceReadOnly", async () => {
    const { container } = render(<AssuranceReadOnly />);
    await expectNoAxeViolations(container);
  });
});
