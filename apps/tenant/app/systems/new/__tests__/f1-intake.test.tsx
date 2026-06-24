/**
 * @jest-environment jsdom
 *
 * F1 visual done-checks (UI-V1-TENANT-SKIN):
 * - TierBadge card variant renders at the resolved-tier step
 * - Override ladder absent when non-system_owner (SodAction structural bar, FE-8)
 */
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { ResolvedTierStep } from "../_steps/resolved-tier-step";
import type { ClassificationRead } from "@irontrust/api-client";

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

const HIGH_CLASSIFICATION: ClassificationRead = {
  id: "cls-1",
  use_case_id: "uc-1",
  tier: "high_risk",
  rationale: "Annex III applies to this system.",
  basis_subcategory_code: "A3-1",
  basis_legal_ref: "EU AI Act Annex III §1",
  status: "pending_review",
  version: 1,
  overridden: false,
  submitted_at: "2024-01-01T00:00:00Z",
} as unknown as ClassificationRead;

function mockMe(roleKeys: string[]) {
  global.fetch = jest.fn((input: RequestInfo | URL) => {
    const url = String(input);
    if (url.includes("/v1/me")) {
      return Promise.resolve({
        ok: true,
        status: 200,
        text: async () =>
          JSON.stringify({
            membership_id: "m1",
            tenant_id: "t1",
            user_id: "u1",
            governance_roles: roleKeys.map((key) => ({ key, display_name: key })),
          }),
        headers: new Headers({ "content-type": "application/json" }),
      } as Response);
    }
    if (url.includes("/v1/eu-subcategories")) {
      return Promise.resolve({
        ok: true,
        status: 200,
        text: async () => JSON.stringify([]),
        headers: new Headers({ "content-type": "application/json" }),
      } as Response);
    }
    return Promise.reject(new Error(`Unexpected fetch: ${url}`));
  });
}

afterEach(() => {
  jest.restoreAllMocks();
});

describe("F1 ResolvedTierStep — TierBadge card variant", () => {
  test("renders TierBadge with data-variant=card", async () => {
    mockMe(["system_owner"]);
    const { container } = render(
      <ResolvedTierStep
        useCaseId="uc-1"
        classification={HIGH_CLASSIFICATION}
        onOverrideApplied={jest.fn()}
        onContinue={jest.fn()}
      />,
      { wrapper }
    );
    const badge = container.querySelector("[data-variant='card']");
    expect(badge).not.toBeNull();
    expect((badge as HTMLElement).dataset.tier).toBe("high");
  });

  test("renders basis text inside card", () => {
    mockMe(["system_owner"]);
    render(
      <ResolvedTierStep
        useCaseId="uc-1"
        classification={HIGH_CLASSIFICATION}
        onOverrideApplied={jest.fn()}
        onContinue={jest.fn()}
      />,
      { wrapper }
    );
    expect(screen.getByText("Annex III applies to this system.")).toBeInTheDocument();
  });

  test("override ladder absent for non-system_owner (SodAction structural bar)", async () => {
    mockMe(["reviewer"]);
    render(
      <ResolvedTierStep
        useCaseId="uc-1"
        classification={HIGH_CLASSIFICATION}
        onOverrideApplied={jest.fn()}
        onContinue={jest.fn()}
      />,
      { wrapper }
    );
    expect(screen.queryByRole("button", { name: /override classification/i })).not.toBeInTheDocument();
  });

  test("Continue button always rendered", () => {
    mockMe(["system_owner"]);
    render(
      <ResolvedTierStep
        useCaseId="uc-1"
        classification={HIGH_CLASSIFICATION}
        onOverrideApplied={jest.fn()}
        onContinue={jest.fn()}
      />,
      { wrapper }
    );
    expect(screen.getByRole("button", { name: /continue/i })).toBeInTheDocument();
  });
});
