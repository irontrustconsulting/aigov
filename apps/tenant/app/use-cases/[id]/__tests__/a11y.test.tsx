/**
 * @jest-environment jsdom
 *
 * axe pass for the use-case assessment surface across major states
 * (WCAG 2.1 AA baseline, FRONTEND §4).
 */
import { render, waitFor, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import type {
  MeRead,
  UseCaseWithClassification,
  UseCaseLifecycleRead,
  SystemRollupRead,
  AssessmentRead,
  AssessmentDetail,
  SectionRead,
  FeederRecommendationRead,
} from "@irontrust/api-client";
import { expectNoAxeViolations } from "../../../../test-utils/axe";
import { AssessmentPageClient } from "../assessment-page-client";

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

const useCaseDetail: UseCaseWithClassification = {
  use_case: {
    id: "uc-1",
    tenant_id: "t1",
    system_id: "sys-1",
    title: "Screen candidate CVs",
    purpose: "Automated screening",
    state: "under_assessment",
    eu_tier: "high_risk",
  },
  classification: {
    id: "cls-1",
    use_case_id: "uc-1",
    tier: "high_risk",
    rationale: "High-risk AI system",
    version: 1,
    is_current: true,
    overridden: false,
    proposed_tier: null,
    basis_subcategory_code: null,
    basis_legal_ref: null,
    requires_context: false,
  },
};

const lifecycle: UseCaseLifecycleRead = {
  use_case_id: "uc-1",
  state: "under_assessment",
  held_from_state: null,
  held_reason: null,
  gates: [],
  blocking: null,
};

const rollup: SystemRollupRead = {
  system_id: "sys-1",
  system_name: "Acme HR Platform",
  use_case_count: 1,
  highest_tier: "high_risk",
  use_cases: [{ use_case_id: "uc-1", title: "Screen candidate CVs", state: "under_assessment", eu_tier: "high_risk", blocking: null }],
};

const draftAiia: AssessmentRead = {
  id: "ass-1",
  use_case_id: "uc-1",
  type: "aiia",
  parent_aiia_id: null,
  status: "draft",
  version: 1,
  tier_snapshot: "high_risk",
  classification_version: 1,
  is_current: true,
  lock_version: 1,
  submission_round: 0,
  submitted_at: null,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

const inReviewAiia: AssessmentRead = { ...draftAiia, id: "ass-2", status: "in_review" };

const emptyDetail: AssessmentDetail = { ...draftAiia, items: [], reviews: [] };
const inReviewDetail: AssessmentDetail = { ...inReviewAiia, items: [], reviews: [] };

const sections: SectionRead[] = [];
const feederRecs: FeederRecommendationRead[] = [];

function mockFetch(meBody: MeRead, assessmentsList: AssessmentRead[], detail: AssessmentDetail) {
  global.fetch = jest.fn((input: RequestInfo | URL) => {
    const url = String(input);
    let body: unknown;
    if (url.includes("/v1/me")) {
      body = meBody;
    } else if (url.includes("/systems/") && url.includes("/rollup")) {
      body = rollup;
    } else if (url.match(/\/use-cases\/[^/]+\/lifecycle/)) {
      body = lifecycle;
    } else if (url.match(/\/use-cases\/[^/]+\/assessments/)) {
      body = assessmentsList;
    } else if (url.match(/\/use-cases\/[^/]+/)) {
      body = useCaseDetail;
    } else if (url.match(/\/assessments\/[^/]+\/sections/)) {
      body = sections;
    } else if (url.match(/\/assessments\/[^/]+\/feeder-recommendations/)) {
      body = feederRecs;
    } else if (url.match(/\/assessments\/[^/]+/)) {
      body = detail;
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

afterEach(() => jest.restoreAllMocks());

test("admin empty-state: axe pass", async () => {
  mockFetch(me([]), [], emptyDetail);
  const { container } = render(<AssessmentPageClient useCaseId="uc-1" />, { wrapper });
  await waitFor(() => screen.getByText(/doesn't hold a governance role/i));
  await expectNoAxeViolations(container);
});

test("system_owner — no-AIIA empty state: axe pass", async () => {
  mockFetch(me(["system_owner"]), [], emptyDetail);
  const { container } = render(<AssessmentPageClient useCaseId="uc-1" />, { wrapper });
  await waitFor(() => screen.getByRole("button", { name: /start assessment/i }));
  await expectNoAxeViolations(container);
});

test("system_owner — DRAFT author mode: axe pass", async () => {
  mockFetch(me(["system_owner"]), [draftAiia], emptyDetail);
  const { container } = render(<AssessmentPageClient useCaseId="uc-1" />, { wrapper });
  await waitFor(() => screen.getByRole("button", { name: /submit for review/i }));
  await expectNoAxeViolations(container);
});

test("system_owner — IN_REVIEW locked: axe pass", async () => {
  mockFetch(me(["system_owner"]), [inReviewAiia], inReviewDetail);
  const { container } = render(<AssessmentPageClient useCaseId="uc-1" />, { wrapper });
  await waitFor(() => screen.getByText("Screen candidate CVs"));
  await expectNoAxeViolations(container);
});

test("contributor — DRAFT view: axe pass", async () => {
  mockFetch(me(["contributor"]), [draftAiia], emptyDetail);
  const { container } = render(<AssessmentPageClient useCaseId="uc-1" />, { wrapper });
  await waitFor(() => screen.getByText("Screen candidate CVs"));
  await expectNoAxeViolations(container);
});
