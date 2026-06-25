/**
 * @jest-environment jsdom
 *
 * UI-F3-ASSESS — four-way role branch assertions (DF2-5, FE-8).
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

const aiia: AssessmentRead = {
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

const assessmentDetail: AssessmentDetail = {
  ...aiia,
  items: [],
  reviews: [],
};

const sections: SectionRead[] = [];
const feederRecs: FeederRecommendationRead[] = [];

function mockFetch(meBody: MeRead, assessmentsList: AssessmentRead[] = [aiia]) {
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
      body = assessmentDetail;
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

describe("AssessmentPageClient — four-way role branch (UI-F3-ASSESS)", () => {
  test("admin: renders empty-state and issues no assessment query (DF2-5)", async () => {
    mockFetch(me([]));

    render(<AssessmentPageClient useCaseId="uc-1" />, { wrapper });

    await waitFor(() =>
      expect(screen.getByText(/doesn't hold a governance role/i)).toBeInTheDocument()
    );

    // No gov:ALL calls — only /v1/me should have been fetched.
    const calls = (global.fetch as jest.Mock).mock.calls.map(([url]: [RequestInfo | URL]) => String(url));
    const assessmentCalls = calls.filter((u) => u.includes("/assessments") || u.includes("/use-cases") || u.includes("/systems"));
    expect(assessmentCalls).toHaveLength(0);
  });

  test("contributor: sees item body but no bootstrap/submit/re-evaluate controls (FE-8)", async () => {
    mockFetch(me(["contributor"]));

    render(<AssessmentPageClient useCaseId="uc-1" />, { wrapper });

    await waitFor(() => expect(screen.getByText("Screen candidate CVs")).toBeInTheDocument());

    // Submit and Start assessment absent; re-evaluate absent (barred via SodAction)
    expect(screen.queryByRole("button", { name: /submit for review/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /start assessment/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /re-evaluate/i })).not.toBeInTheDocument();
  });

  test("assurance (reviewer): renders read-only view without author controls", async () => {
    mockFetch(me(["reviewer"]));

    render(<AssessmentPageClient useCaseId="uc-1" />, { wrapper });

    await waitFor(() => expect(screen.getByText("Screen candidate CVs")).toBeInTheDocument());

    expect(screen.queryByRole("button", { name: /submit for review/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /start assessment/i })).not.toBeInTheDocument();
  });

  test("system_owner: renders start-assessment button when no AIIA exists", async () => {
    mockFetch(me(["system_owner"]), []);

    render(<AssessmentPageClient useCaseId="uc-1" />, { wrapper });

    await waitFor(() =>
      expect(screen.getByRole("button", { name: /start assessment/i })).toBeInTheDocument()
    );
  });

  test("system_owner: renders submit button for DRAFT assessment (FE-6 live)", async () => {
    mockFetch(me(["system_owner"]));

    render(<AssessmentPageClient useCaseId="uc-1" />, { wrapper });

    await waitFor(() =>
      expect(screen.getByRole("button", { name: /submit for review/i })).toBeInTheDocument()
    );
  });

  test("contributor: when no AIIA exists, shows owner-must-start message (no bootstrap button)", async () => {
    mockFetch(me(["contributor"]), []);

    render(<AssessmentPageClient useCaseId="uc-1" />, { wrapper });

    await waitFor(() =>
      expect(screen.getByText(/a system owner must start/i)).toBeInTheDocument()
    );
    expect(screen.queryByRole("button", { name: /start assessment/i })).not.toBeInTheDocument();
  });
});
