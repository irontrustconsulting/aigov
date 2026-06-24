/**
 * @jest-environment jsdom
 *
 * F3 visual done-checks (UI-V1-TENANT-SKIN):
 * - AssessmentHeader renders compact TierBadge for eu_tier
 * - AI_SUGGESTED item renders dashed ProvenanceBadge + confirm/amend gate
 * - Author controls absent for non-system_owner
 */
import { render, screen } from "@testing-library/react";
import { AssessmentHeader } from "../_regions/assessment-header";
import { ItemCard } from "../_regions/item-card";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import type { AssessmentItemRead } from "@irontrust/api-client";

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

function mockFetch() {
  global.fetch = jest.fn(() =>
    Promise.resolve({
      ok: true, status: 200,
      text: async () => JSON.stringify([]),
      headers: new Headers({ "content-type": "application/json" }),
    } as Response)
  );
}

afterEach(() => { jest.restoreAllMocks(); });

const AI_SUGGESTED_ITEM: AssessmentItemRead = {
  id: "item-1",
  assessment_id: "aiia-1",
  prompt: "Does this system process personal data?",
  response: null,
  treatment_decision: null,
  provenance: "ai_suggested",
  lock_version: 1,
  source_assessment_id: null,
  source_ref: null,
  surfaces_into: false,
  evidence_links: [],
  control_links: [],
} as unknown as AssessmentItemRead;

describe("F3 AssessmentHeader — compact TierBadge", () => {
  test("renders data-variant=compact TierBadge for eu_tier", () => {
    const { container } = render(
      <AssessmentHeader
        useCaseId="uc-1"
        useCaseTitle="Credit scoring"
        euTier={"high_risk" as any}
        systemName="Risk Tool"
        court={null}
        roleKeys={new Set(["system_owner"])}
        branch="system_owner"
      />,
      { wrapper }
    );
    const badge = container.querySelector("[data-variant='compact'][data-tier='high']");
    expect(badge).not.toBeNull();
  });

  test("no eu-tier paragraph when euTier is null", () => {
    render(
      <AssessmentHeader
        useCaseId="uc-1"
        useCaseTitle="Credit scoring"
        euTier={null}
        systemName={null}
        court={null}
        roleKeys={new Set(["reviewer"])}
        branch="reviewer"
      />,
      { wrapper }
    );
    expect(document.querySelector("[aria-label='eu-tier']")).toBeNull();
  });
});

describe("F3 ItemCard — AI_SUGGESTED item disposition gate", () => {
  test("AI_SUGGESTED item renders ProvenanceBadge with dashed border", () => {
    mockFetch();
    const { container } = render(
      <ItemCard
        item={AI_SUGGESTED_ITEM}
        assessmentId="aiia-1"
        isLocked={false}
        canWrite={true}
        isFederSurfaced={false}
      />,
      { wrapper }
    );
    const badge = container.querySelector(".border-dashed");
    expect(badge).not.toBeNull();
    expect(badge?.textContent).toContain("AI suggested");
  });

  test("AI_SUGGESTED response textarea disabled until confirmed (authoring gate)", () => {
    mockFetch();
    render(
      <ItemCard
        item={AI_SUGGESTED_ITEM}
        assessmentId="aiia-1"
        isLocked={false}
        canWrite={true}
        isFederSurfaced={false}
      />,
      { wrapper }
    );
    const textarea = screen.getByLabelText("Response") as HTMLTextAreaElement;
    expect(textarea.disabled).toBe(true);
  });

  test("author controls (Delete) absent for reviewer branch (canWrite=false)", () => {
    mockFetch();
    render(
      <ItemCard
        item={AI_SUGGESTED_ITEM}
        assessmentId="aiia-1"
        isLocked={false}
        canWrite={false}
        isFederSurfaced={false}
      />,
      { wrapper }
    );
    expect(screen.queryByRole("button", { name: /delete/i })).not.toBeInTheDocument();
  });
});
