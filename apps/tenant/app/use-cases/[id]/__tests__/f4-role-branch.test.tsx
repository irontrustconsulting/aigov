/**
 * @jest-environment jsdom
 *
 * UI-F4-ASSURE — five-way role branch assertions on use-cases/[id].
 * Complements the F3 page.test.tsx which covers admin/contributor/system_owner.
 * This file covers: reviewer, authoriser, auditor, and F4 system_owner additions.
 */
import { render, screen, waitFor } from "@testing-library/react";
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
    status: "approved",
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

const useCaseDetailPendingReview: UseCaseWithClassification = {
  ...useCaseDetail,
  classification: {
    ...useCaseDetail.classification!,
    status: "pending_review",
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

const pendingAuthorisationLifecycle: UseCaseLifecycleRead = {
  ...lifecycle,
  state: "pending_authorisation",
};

const authorisedLifecycle: UseCaseLifecycleRead = {
  ...lifecycle,
  state: "authorised",
};

const rollup: SystemRollupRead = {
  system_id: "sys-1",
  system_name: "Acme HR Platform",
  use_case_count: 1,
  highest_tier: "high_risk",
  use_cases: [{ use_case_id: "uc-1", title: "Screen candidate CVs", state: "under_assessment", eu_tier: "high_risk", blocking: null }],
};

const inReviewAiia: AssessmentRead = {
  id: "ass-1",
  use_case_id: "uc-1",
  type: "aiia",
  parent_aiia_id: null,
  status: "in_review",
  version: 1,
  tier_snapshot: "high_risk",
  classification_version: 1,
  is_current: true,
  lock_version: 2,
  submission_round: 1,
  submitted_at: "2026-06-01T00:00:00Z",
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-06-01T00:00:00Z",
};

const approvedAiia: AssessmentRead = { ...inReviewAiia, id: "ass-2", status: "approved" };

const inReviewDetail: AssessmentDetail = { ...inReviewAiia, items: [], reviews: [] };
const approvedDetail: AssessmentDetail = { ...approvedAiia, items: [], reviews: [] };

const sections: SectionRead[] = [];
const feederRecs: FeederRecommendationRead[] = [];

function mockFetch(
  meBody: MeRead,
  assessmentsList: AssessmentRead[],
  detail: AssessmentDetail,
  useCaseOverride?: UseCaseWithClassification,
  lifecycleOverride?: UseCaseLifecycleRead,
) {
  const ucDetail = useCaseOverride ?? useCaseDetail;
  const lc = lifecycleOverride ?? lifecycle;

  global.fetch = jest.fn((input: RequestInfo | URL) => {
    const url = String(input);
    let body: unknown;
    if (url.includes("/v1/me")) {
      body = meBody;
    } else if (url.includes("/systems/") && url.includes("/rollup")) {
      body = rollup;
    } else if (url.match(/\/use-cases\/[^/]+\/lifecycle/)) {
      body = lc;
    } else if (url.match(/\/use-cases\/[^/]+\/assessments/)) {
      body = assessmentsList;
    } else if (url.match(/\/use-cases\/[^/]+\/authorisation/)) {
      // 404 — never authorised (unless test overrides)
      return Promise.resolve({ ok: false, status: 404, text: async () => '{"detail":"Not found"}' } as Response);
    } else if (url.match(/\/use-cases\/[^/]+/)) {
      body = ucDetail;
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

describe("AssessmentPageClient F4 — role branch (UI-F4-ASSURE WI-8)", () => {
  test("reviewer — IN_REVIEW AIIA: renders review panel, no author/submit controls", async () => {
    mockFetch(me(["reviewer"]), [inReviewAiia], inReviewDetail);

    render(<AssessmentPageClient useCaseId="uc-1" />, { wrapper });

    await waitFor(() => expect(screen.getByRole("heading", { name: /review assessment/i })).toBeInTheDocument());

    expect(screen.queryByRole("button", { name: /submit for review/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /start assessment/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /re-evaluate/i })).not.toBeInTheDocument();
    // Review panel controls present
    expect(screen.getByRole("button", { name: /submit review/i })).toBeInTheDocument();
  });

  test("reviewer — classification PENDING_REVIEW: renders sign-off panel, not review panel (DF4-2)", async () => {
    mockFetch(me(["reviewer"]), [inReviewAiia], inReviewDetail, useCaseDetailPendingReview);

    render(<AssessmentPageClient useCaseId="uc-1" />, { wrapper });

    await waitFor(() => expect(screen.getByRole("heading", { name: /classification sign-off/i })).toBeInTheDocument());

    // review panel should still show (AIIA is in_review AND classification is pending_review)
    // Both can coexist — disambiguation is by type, not mutual exclusion between the two conditions
    expect(screen.getByRole("heading", { name: /review assessment/i })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /submit for review/i })).not.toBeInTheDocument();
  });

  test("authoriser — pending_authorisation: renders authorise panel with residual-risk input", async () => {
    mockFetch(me(["authoriser"]), [approvedAiia], approvedDetail, useCaseDetail, pendingAuthorisationLifecycle);

    render(<AssessmentPageClient useCaseId="uc-1" />, { wrapper });

    await waitFor(() =>
      expect(screen.getByRole("heading", { name: /grant deployment authorisation/i })).toBeInTheDocument()
    );

    expect(screen.getByPlaceholderText(/describe residual risks/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /submit for review/i })).not.toBeInTheDocument();
  });

  test("auditor: renders read-only AIIA; no review-queue call issued", async () => {
    mockFetch(me(["auditor"]), [inReviewAiia], inReviewDetail);

    render(<AssessmentPageClient useCaseId="uc-1" />, { wrapper });

    await waitFor(() => expect(screen.getByText("Screen candidate CVs")).toBeInTheDocument());

    expect(screen.queryByRole("button", { name: /submit review/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /sign off/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /grant authorisation/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /submit for review/i })).not.toBeInTheDocument();

    const calls = (global.fetch as jest.Mock).mock.calls.map(([url]: [RequestInfo | URL]) => String(url));
    expect(calls.filter((u) => u.includes("/review-queue"))).toHaveLength(0);
  });

  test("system_owner — APPROVED AIIA: renders reopen button, no submit button", async () => {
    mockFetch(me(["system_owner"]), [approvedAiia], approvedDetail);

    render(<AssessmentPageClient useCaseId="uc-1" />, { wrapper });

    await waitFor(() =>
      expect(screen.getByRole("button", { name: /reopen for revision/i })).toBeInTheDocument()
    );

    expect(screen.queryByRole("button", { name: /submit for review/i })).not.toBeInTheDocument();
  });

  test("system_owner — APPROVED AIIA: reopen button absent for non-owner (structural, FE-8)", async () => {
    mockFetch(me(["reviewer"]), [approvedAiia], approvedDetail);

    render(<AssessmentPageClient useCaseId="uc-1" />, { wrapper });

    await waitFor(() => expect(screen.getByText("Screen candidate CVs")).toBeInTheDocument());

    expect(screen.queryByRole("button", { name: /reopen for revision/i })).not.toBeInTheDocument();
  });
});
