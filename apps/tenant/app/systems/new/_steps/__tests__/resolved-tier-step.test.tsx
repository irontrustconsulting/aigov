/**
 * @jest-environment jsdom
 */
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import type { ClassificationRead } from "@irontrust/api-client";
import { ResolvedTierStep } from "../resolved-tier-step";

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

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

const subcategories = [
  { id: "s1", code: "HR-1", name: "High risk sub A", description: null, category_id: "cat-1", tier: "high_risk" },
  { id: "s2", code: "LR-1", name: "Limited risk sub", description: null, category_id: "cat-1", tier: "limited_risk" },
];

function mockFetch({ isSystemOwner }: { isSystemOwner: boolean }) {
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
            role: "member",
            email: null,
            name: null,
            tenant_name: "Acme Corp",
            governance_roles: isSystemOwner ? [{ id: "g1", key: "system_owner", name: "System Owner", description: null, line_of_defence: 1 }] : [],
          }),
      } as Response);
    }
    if (url.includes("eu-ai-act/subcategories")) {
      return Promise.resolve({ ok: true, status: 200, text: async () => JSON.stringify(subcategories) } as Response);
    }
    if (url.includes("classify/override")) {
      return Promise.resolve({
        ok: true,
        status: 200,
        text: async () =>
          JSON.stringify({
            use_case: { id: "uc-1", tenant_id: "t1", system_id: "sys-1", title: "x", purpose: null, state: "intake", eu_tier: "high_risk" },
            classification: { ...classification, tier: "high_risk", overridden: true },
          }),
      } as Response);
    }
    return Promise.resolve({ ok: true, status: 200, text: async () => JSON.stringify([]) } as Response);
  }) as jest.Mock;
}

afterEach(() => jest.restoreAllMocks());

describe("ResolvedTierStep", () => {
  test("renders tier and basis reasoning-first, and offers the override control to a system_owner", async () => {
    mockFetch({ isSystemOwner: true });
    render(
      <ResolvedTierStep
        useCaseId="uc-1"
        classification={classification}
        onOverrideApplied={jest.fn()}
        onContinue={jest.fn()}
      />,
      { wrapper }
    );

    // TierBadge card renders the display label, not the raw DB tier string
    // toTierMember("high_risk") → "HIGH" → data-tier="high"
    expect(document.querySelector("[data-tier='high'][data-variant='card']")).not.toBeNull();
    expect(screen.getByText("Mapped via product category")).toBeInTheDocument();
    expect(screen.getByText(/Art\. 6\(2\)/)).toBeInTheDocument();

    await waitFor(() =>
      expect(screen.getByRole("button", { name: /override classification/i })).toBeInTheDocument()
    );
  });

  test("the override control is absent (not disabled) for a non-system_owner — structural SoD bar", async () => {
    mockFetch({ isSystemOwner: false });
    render(
      <ResolvedTierStep
        useCaseId="uc-1"
        classification={classification}
        onOverrideApplied={jest.fn()}
        onContinue={jest.fn()}
      />,
      { wrapper }
    );

    await waitFor(() =>
      expect(document.querySelector("[data-tier='high'][data-variant='card']")).not.toBeNull()
    );
    expect(screen.queryByRole("button", { name: /override classification/i })).not.toBeInTheDocument();
  });

  test("a mismatched tier/subcategory pair is unreachable — subcategory options narrow to the chosen tier", async () => {
    mockFetch({ isSystemOwner: true });
    render(
      <ResolvedTierStep
        useCaseId="uc-1"
        classification={classification}
        onOverrideApplied={jest.fn()}
        onContinue={jest.fn()}
      />,
      { wrapper }
    );

    await waitFor(() => screen.getByRole("button", { name: /override classification/i }));
    fireEvent.click(screen.getByRole("button", { name: /override classification/i }));

    await waitFor(() => screen.getByLabelText("Subcategory"));
    const subcategorySelect = screen.getByLabelText("Subcategory") as HTMLSelectElement;
    // Filter out the placeholder "" added by the SingleSelect FE-4 ALTER (INV-81).
    const optionValues = Array.from(subcategorySelect.options).map((o) => o.value).filter((v) => v !== "");
    expect(optionValues).toEqual(["HR-1"]); // limited_risk sub excluded — tier defaults to classification.tier (high_risk)
    expect(optionValues).not.toContain("LR-1");

    fireEvent.change(screen.getByLabelText("Tier"), { target: { value: "limited_risk" } });
    await waitFor(() => {
      const updated = screen.getByLabelText("Subcategory") as HTMLSelectElement;
      const values = Array.from(updated.options).map((o) => o.value).filter((v) => v !== "");
      expect(values).toEqual(["LR-1"]);
    });
  });

  test("a successful override calls onOverrideApplied with the new classification", async () => {
    mockFetch({ isSystemOwner: true });
    const onOverrideApplied = jest.fn();
    render(
      <ResolvedTierStep
        useCaseId="uc-1"
        classification={classification}
        onOverrideApplied={onOverrideApplied}
        onContinue={jest.fn()}
      />,
      { wrapper }
    );

    await waitFor(() => screen.getByRole("button", { name: /override classification/i }));
    fireEvent.click(screen.getByRole("button", { name: /override classification/i }));
    await waitFor(() => screen.getByLabelText("Subcategory"));
    fireEvent.change(screen.getByLabelText("Subcategory"), { target: { value: "HR-1" } });
    fireEvent.click(screen.getByRole("button", { name: /confirm override/i }));

    await waitFor(() => expect(onOverrideApplied).toHaveBeenCalled());
  });
});
