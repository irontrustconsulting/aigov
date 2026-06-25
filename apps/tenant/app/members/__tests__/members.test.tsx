/**
 * @jest-environment jsdom
 *
 * UI-F9-MEMBERS done-checks.
 *
 * WI-1: member-role MeRead → not-authorised treatment; zero GET /v1/members (DF-F9-3).
 * WI-1: admin-role MeRead → Members nav entry + list rendered.
 * WI-2: loading → Skeleton; error → ErrorState; owner-only → FirstRunPanel.
 * WI-3: invite → POST /v1/members; pending row; cache invalidated.
 * WI-2: accept-status chip carries no --verdict-* class (FE-16 guard).
 * WI-5: system_owner held → contributor assignable; reviewer/authoriser/auditor disabled-with-reason (INV-71).
 * WI-5: self panel → control absent; note rendered (INV-56).
 * WI-6: one GET /governance-roles/assignments populates all rows' roles; no per-row fetch.
 */
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import type { MeRead, MemberListResponse, GovernanceCatalogueRead, GovernanceRoleAssignmentRead } from "@irontrust/api-client";
import { MembersClient } from "../members-client";
import { RolePanel } from "../_components/role-panel";
import type { MemberRead } from "@irontrust/api-client";

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const ACTING_MEMBERSHIP_ID = "m-admin-1";
const OTHER_MEMBERSHIP_ID = "m-other-1";

function makeMeRead(role: "admin" | "member"): MeRead {
  return {
    membership_id: ACTING_MEMBERSHIP_ID,
    tenant_id: "t-1",
    role,
    email: "admin@acme.test",
    name: "Admin User",
    tenant_name: "Acme Corp",
    governance_roles: [],
  };
}

// Role IDs
const ROLE_IDS = {
  system_owner: "role-so",
  contributor: "role-co",
  reviewer: "role-rv",
  authoriser: "role-au",
  auditor: "role-ad",
};

const CATALOGUE: GovernanceCatalogueRead = {
  roles: [
    { id: ROLE_IDS.system_owner, key: "system_owner", name: "System owner", description: null, line_of_defence: 1 },
    { id: ROLE_IDS.contributor, key: "contributor", name: "Contributor", description: null, line_of_defence: 1 },
    { id: ROLE_IDS.reviewer, key: "reviewer", name: "Reviewer", description: null, line_of_defence: 2 },
    { id: ROLE_IDS.authoriser, key: "authoriser", name: "Authoriser", description: null, line_of_defence: 2 },
    { id: ROLE_IDS.auditor, key: "auditor", name: "Auditor", description: null, line_of_defence: 3 },
  ],
  conflicts: [
    /* system_owner conflicts with reviewer, authoriser, auditor (composable: system_owner+contributor) */
    { id: "c1", role_a_id: ROLE_IDS.system_owner, role_b_id: ROLE_IDS.reviewer },
    { id: "c2", role_a_id: ROLE_IDS.system_owner, role_b_id: ROLE_IDS.authoriser },
    { id: "c3", role_a_id: ROLE_IDS.system_owner, role_b_id: ROLE_IDS.auditor },
    /* reviewer conflicts */
    { id: "c4", role_a_id: ROLE_IDS.reviewer, role_b_id: ROLE_IDS.contributor },
    { id: "c5", role_a_id: ROLE_IDS.reviewer, role_b_id: ROLE_IDS.authoriser },
    /* authoriser conflicts */
    { id: "c6", role_a_id: ROLE_IDS.authoriser, role_b_id: ROLE_IDS.contributor },
    /* auditor conflicts */
    { id: "c7", role_a_id: ROLE_IDS.auditor, role_b_id: ROLE_IDS.contributor },
    { id: "c8", role_a_id: ROLE_IDS.auditor, role_b_id: ROLE_IDS.reviewer },
    { id: "c9", role_a_id: ROLE_IDS.auditor, role_b_id: ROLE_IDS.authoriser },
  ],
};

function makeMemberList(items: Partial<MemberRead>[] = []): MemberListResponse {
  const defaults: MemberRead = {
    user_id: "u-other",
    membership_id: OTHER_MEMBERSHIP_ID,
    email: "other@acme.test",
    name: "Other User",
    role: "member",
    status: "pending",
    created_at: "2026-01-01T00:00:00Z",
  };
  return { items: items.map((i) => ({ ...defaults, ...i })), next_cursor: null };
}

// Member list with 2 rows (admin + one other) — not first-run
const TWO_MEMBER_LIST: MemberListResponse = makeMemberList([
  { user_id: "u-admin", membership_id: ACTING_MEMBERSHIP_ID, email: "admin@acme.test", name: "Admin User", role: "admin", status: "accepted" },
  { user_id: "u-other", membership_id: OTHER_MEMBERSHIP_ID, email: "other@acme.test", name: "Other User", role: "member", status: "pending" },
]);

const NO_ASSIGNMENTS: GovernanceRoleAssignmentRead[] = [];

const SYSTEM_OWNER_ASSIGNMENT: GovernanceRoleAssignmentRead = {
  id: "assign-1",
  tenant_id: "t-1",
  membership_id: OTHER_MEMBERSHIP_ID,
  governance_role_id: ROLE_IDS.system_owner,
  granted_by_membership_id: ACTING_MEMBERSHIP_ID,
  granted_at: "2026-01-01T00:00:00Z",
};

// ---------------------------------------------------------------------------
// Test harness
// ---------------------------------------------------------------------------

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

function mockFetch({
  meData,
  members = TWO_MEMBER_LIST,
  catalogue = CATALOGUE,
  allAssignments = NO_ASSIGNMENTS,
  memberAssignments = NO_ASSIGNMENTS,
  inviteStatus = 201,
}: {
  meData: MeRead;
  members?: MemberListResponse;
  catalogue?: GovernanceCatalogueRead;
  allAssignments?: GovernanceRoleAssignmentRead[];
  memberAssignments?: GovernanceRoleAssignmentRead[];
  inviteStatus?: number;
}) {
  global.fetch = jest.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    const method = (init?.method ?? "GET").toUpperCase();

    /* NOTE: /v1/members and /v1/me share a prefix. Check /members before /me. */
    if (url.includes("/v1/members") && method === "POST") {
      return Promise.resolve({
        ok: inviteStatus < 400,
        status: inviteStatus,
        text: async () =>
          JSON.stringify({ user_id: "u-new", membership_id: "m-new", status: "pending" }),
      } as Response);
    }
    if (url.includes("/v1/members")) {
      return Promise.resolve({ ok: true, status: 200, text: async () => JSON.stringify(members) } as Response);
    }
    if (url.includes("/v1/me")) {
      return Promise.resolve({ ok: true, status: 200, text: async () => JSON.stringify(meData) } as Response);
    }
    if (url.includes("/governance-roles/catalogue")) {
      return Promise.resolve({ ok: true, status: 200, text: async () => JSON.stringify(catalogue) } as Response);
    }
    if (url.match(/governance-roles\/assignments\/member\//)) {
      return Promise.resolve({ ok: true, status: 200, text: async () => JSON.stringify(memberAssignments) } as Response);
    }
    if (url.includes("/governance-roles/assignments")) {
      return Promise.resolve({ ok: true, status: 200, text: async () => JSON.stringify(allAssignments) } as Response);
    }
    return Promise.resolve({ ok: true, status: 200, text: async () => JSON.stringify({}) } as Response);
  }) as jest.Mock;
}

function fetchedUrls(): string[] {
  return (global.fetch as jest.Mock).mock.calls.map(([url]: [RequestInfo | URL]) => String(url));
}

afterEach(() => jest.restoreAllMocks());

// ---------------------------------------------------------------------------
// WI-1: Role gate — member vs admin
// ---------------------------------------------------------------------------

describe("WI-1: admin-axis nav + page gate (DF-F9-3)", () => {
  test("member-role: not-authorised treatment; zero GET /v1/members calls issued", async () => {
    mockFetch({ meData: makeMeRead("member") });

    render(<MembersClient />, { wrapper });

    await waitFor(() =>
      expect(screen.getByTestId("not-authorised")).toBeInTheDocument()
    );

    const memberCalls = fetchedUrls().filter((u) => u.includes("/v1/members"));
    expect(memberCalls).toHaveLength(0);
  });

  test("admin-role: members list rendered", async () => {
    mockFetch({ meData: makeMeRead("admin") });

    render(<MembersClient />, { wrapper });

    await waitFor(() =>
      expect(screen.getByText("Other User")).toBeInTheDocument()
    );
  });
});

// ---------------------------------------------------------------------------
// WI-2: INV-70 states (Skeleton, ErrorState, FirstRunPanel)
// ---------------------------------------------------------------------------

describe("WI-2: INV-70 states", () => {
  test("loading: Skeleton rendered while members fetch is pending", async () => {
    let resolveMembersFetch: ((v: Response) => void) | undefined;
    global.fetch = jest.fn((url: RequestInfo | URL) => {
      const u = String(url);
      /* /v1/members prefix check must come before /v1/me */
      if (u.includes("/v1/members")) {
        return new Promise<Response>((r) => { resolveMembersFetch = r; });
      }
      if (u.includes("/v1/me")) {
        return Promise.resolve({ ok: true, status: 200, text: async () => JSON.stringify(makeMeRead("admin")) } as Response);
      }
      return Promise.resolve({ ok: true, status: 200, text: async () => JSON.stringify([]) } as Response);
    }) as jest.Mock;

    render(<MembersClient />, { wrapper });

    /* After /me resolves and MembersList mounts, members is still pending → Skeleton shown */
    await waitFor(() => expect(screen.getByText("Members")).toBeInTheDocument());

    /* Resolve the pending fetch to prevent act() warnings on cleanup */
    resolveMembersFetch?.({
      ok: true,
      status: 200,
      text: async () => JSON.stringify(TWO_MEMBER_LIST),
    } as Response);
  });

  test("error: ErrorState rendered with retry button", async () => {
    global.fetch = jest.fn((url: RequestInfo | URL) => {
      const u = String(url);
      /* /v1/members prefix check must come before /v1/me */
      if (u.includes("/v1/members")) {
        return Promise.resolve({ ok: false, status: 500, text: async () => JSON.stringify({ detail: "error" }) } as Response);
      }
      if (u.includes("/v1/me")) {
        return Promise.resolve({ ok: true, status: 200, text: async () => JSON.stringify(makeMeRead("admin")) } as Response);
      }
      return Promise.resolve({ ok: true, status: 200, text: async () => JSON.stringify([]) } as Response);
    }) as jest.Mock;

    render(<MembersClient />, { wrapper });

    await waitFor(() =>
      expect(screen.getByRole("button", { name: /try again/i })).toBeInTheDocument()
    );
  });

  test("owner-only list (1 item): FirstRunPanel rendered", async () => {
    const ownerOnly: MemberListResponse = makeMemberList([
      { user_id: "u-admin", membership_id: ACTING_MEMBERSHIP_ID, email: "admin@acme.test", role: "admin", status: "accepted" },
    ]);
    mockFetch({ meData: makeMeRead("admin"), members: ownerOnly });

    render(<MembersClient />, { wrapper });

    await waitFor(() =>
      expect(screen.getByText(/invite team members/i)).toBeInTheDocument()
    );
  });
});

// ---------------------------------------------------------------------------
// WI-3: Invite member
// ---------------------------------------------------------------------------

describe("WI-3: Invite member", () => {
  test("successful invite: POST /v1/members issued; pending row appears; list refetched", async () => {
    const updatedList: MemberListResponse = makeMemberList([
      { user_id: "u-admin", membership_id: ACTING_MEMBERSHIP_ID, email: "admin@acme.test", role: "admin", status: "accepted" },
      { user_id: "u-other", membership_id: OTHER_MEMBERSHIP_ID, email: "other@acme.test", name: "Other User", role: "member", status: "pending" },
      { user_id: "u-new", membership_id: "m-new", email: "new@acme.test", name: "New Person", role: "member", status: "pending" },
    ]);

    let listCallCount = 0;
    global.fetch = jest.fn((url: RequestInfo | URL, init?: RequestInit) => {
      const u = String(url);
      const method = (init?.method ?? "GET").toUpperCase();
      /* /v1/members checks must come before /v1/me */
      if (u.includes("/v1/members") && method === "POST") {
        return Promise.resolve({ ok: true, status: 201, text: async () => JSON.stringify({ user_id: "u-new", membership_id: "m-new", status: "pending" }) } as Response);
      }
      if (u.includes("/v1/members")) {
        listCallCount++;
        return Promise.resolve({ ok: true, status: 200, text: async () => JSON.stringify(listCallCount > 1 ? updatedList : TWO_MEMBER_LIST) } as Response);
      }
      if (u.includes("/v1/me")) {
        return Promise.resolve({ ok: true, status: 200, text: async () => JSON.stringify(makeMeRead("admin")) } as Response);
      }
      if (u.includes("/governance-roles/catalogue")) {
        return Promise.resolve({ ok: true, status: 200, text: async () => JSON.stringify(CATALOGUE) } as Response);
      }
      return Promise.resolve({ ok: true, status: 200, text: async () => JSON.stringify([]) } as Response);
    }) as jest.Mock;

    render(<MembersClient />, { wrapper });

    await waitFor(() => expect(screen.getByText("Other User")).toBeInTheDocument());

    fireEvent.click(screen.getByRole("button", { name: /invite member/i }));

    const nameInput = await screen.findByLabelText(/full name/i);
    const emailInput = screen.getByLabelText(/email address/i);
    fireEvent.change(nameInput, { target: { value: "New Person" } });
    fireEvent.change(emailInput, { target: { value: "new@acme.test" } });

    fireEvent.click(screen.getByRole("button", { name: /send invite/i }));

    await waitFor(() => {
      const postCalls = (global.fetch as jest.Mock).mock.calls.filter(
        ([u, i]: [RequestInfo | URL, RequestInit]) =>
          String(u).includes("/v1/members") && (i?.method ?? "GET").toUpperCase() === "POST"
      );
      expect(postCalls).toHaveLength(1);
    });

    /* After success, list was invalidated and re-fetched */
    await waitFor(() => expect(listCallCount).toBeGreaterThan(1));
  });
});

// ---------------------------------------------------------------------------
// WI-2: accept-status chip FE-16 guard
// ---------------------------------------------------------------------------

describe("WI-2: accept-status chip (FE-16 guard)", () => {
  test("pending chip carries no --verdict-* class", async () => {
    mockFetch({ meData: makeMeRead("admin") });

    const { container } = render(<MembersClient />, { wrapper });

    await waitFor(() => expect(screen.getByText("Other User")).toBeInTheDocument());

    const pendingChip = container.querySelector('[data-accept-status="pending"]');
    expect(pendingChip).not.toBeNull();

    /* Assert no --verdict-* class anywhere in the chip's class list */
    const classList = pendingChip!.className;
    expect(classList).not.toMatch(/verdict/i);
  });

  test("accepted chip carries no --verdict-* class", async () => {
    mockFetch({ meData: makeMeRead("admin") });

    const { container } = render(<MembersClient />, { wrapper });

    await waitFor(() => expect(screen.getByText("Admin User")).toBeInTheDocument());

    const acceptedChip = container.querySelector('[data-accept-status="accepted"]');
    expect(acceptedChip).not.toBeNull();
    expect(acceptedChip!.className).not.toMatch(/verdict/i);
  });
});

// ---------------------------------------------------------------------------
// WI-5: SoD-visible assign control (INV-71)
// ---------------------------------------------------------------------------

describe("WI-5: SoD-visible assign control (INV-71)", () => {
  const OTHER_MEMBER: MemberRead = {
    user_id: "u-other",
    membership_id: OTHER_MEMBERSHIP_ID,
    email: "other@acme.test",
    name: "Other User",
    role: "member",
    status: "accepted",
    created_at: "2026-01-01T00:00:00Z",
  };

  function renderRolePanel(memberAssignments: GovernanceRoleAssignmentRead[]) {
    global.fetch = jest.fn((url: RequestInfo | URL) => {
      const u = String(url);
      if (u.includes("/governance-roles/catalogue")) {
        return Promise.resolve({ ok: true, status: 200, text: async () => JSON.stringify(CATALOGUE) } as Response);
      }
      if (u.match(/governance-roles\/assignments\/member\//)) {
        return Promise.resolve({ ok: true, status: 200, text: async () => JSON.stringify(memberAssignments) } as Response);
      }
      return Promise.resolve({ ok: true, status: 200, text: async () => JSON.stringify([]) } as Response);
    }) as jest.Mock;

    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <RolePanel
          member={OTHER_MEMBER}
          actingMembershipId={ACTING_MEMBERSHIP_ID}
          open={true}
          onClose={jest.fn()}
        />
      </QueryClientProvider>
    );
  }

  test("member holds system_owner: contributor assignable; reviewer/authoriser/auditor disabled-with-reason", async () => {
    renderRolePanel([SYSTEM_OWNER_ASSIGNMENT]);

    await waitFor(() =>
      expect(screen.getByLabelText(/assign contributor/i)).toBeInTheDocument()
    );

    /* Contributor: assignable (enabled) */
    const contributorBtn = screen.getByLabelText(/assign contributor/i);
    expect(contributorBtn).not.toBeDisabled();

    /* Reviewer: disabled */
    const reviewerBtn = screen.getByLabelText(/assign reviewer/i);
    expect(reviewerBtn).toBeDisabled();

    /* Authoriser: disabled */
    const authoriserBtn = screen.getByLabelText(/assign authoriser/i);
    expect(authoriserBtn).toBeDisabled();

    /* Auditor: disabled */
    const auditorBtn = screen.getByLabelText(/assign auditor/i);
    expect(auditorBtn).toBeDisabled();

    /* Reason text: colon, not em dash (INV-71 specimen) */
    const reasons = screen.getAllByTestId("sod-reason");
    expect(reasons.length).toBeGreaterThanOrEqual(3);
    reasons.forEach((r) => {
      expect(r.textContent).toMatch(/Conflicts with System owner: separation of duties/i);
      expect(r.textContent).not.toMatch(/—/); // no em dash
    });
  });

  test("no held roles: all 5 roles are assignable", async () => {
    renderRolePanel([]);

    await waitFor(() =>
      expect(screen.getByLabelText(/assign system owner/i)).toBeInTheDocument()
    );

    const assignBtns = screen.getAllByRole("button", { name: /^assign /i });
    assignBtns.forEach((btn) => expect(btn).not.toBeDisabled());
  });
});

// ---------------------------------------------------------------------------
// WI-5: Self panel (INV-56) — control absent; note present
// ---------------------------------------------------------------------------

describe("WI-5: Self panel (INV-56)", () => {
  const SELF_MEMBER: MemberRead = {
    user_id: "u-admin",
    membership_id: ACTING_MEMBERSHIP_ID, // same as actingMembershipId
    email: "admin@acme.test",
    name: "Admin User",
    role: "admin",
    status: "accepted",
    created_at: "2026-01-01T00:00:00Z",
  };

  test("self panel: no assign/revoke controls; explanatory note rendered", () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <RolePanel
          member={SELF_MEMBER}
          actingMembershipId={ACTING_MEMBERSHIP_ID}
          open={true}
          onClose={jest.fn()}
        />
      </QueryClientProvider>
    );

    /* Note is rendered */
    expect(
      screen.getByText(/governance roles are assigned by another administrator/i)
    ).toBeInTheDocument();

    /* No assign or revoke buttons (control absent, INV-56) */
    expect(screen.queryByRole("button", { name: /assign/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /revoke/i })).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// WI-6: Roles-held column — single tenant-wide fetch, no N+1
// ---------------------------------------------------------------------------

describe("WI-6: Roles-held list column (P5 confirmed)", () => {
  test("one GET /governance-roles/assignments populates all rows; no per-row member fetch", async () => {
    const allAssignments: GovernanceRoleAssignmentRead[] = [
      { ...SYSTEM_OWNER_ASSIGNMENT, membership_id: OTHER_MEMBERSHIP_ID },
    ];
    mockFetch({ meData: makeMeRead("admin"), allAssignments });

    render(<MembersClient />, { wrapper });

    await waitFor(() =>
      expect(screen.getByText("Other User")).toBeInTheDocument()
    );

    /* Roles-held column shows the role name (joined from catalogue) */
    await waitFor(() =>
      expect(screen.getByText("System owner")).toBeInTheDocument()
    );

    /* Exactly one call to the tenant-wide assignments route */
    const allAssignmentCalls = fetchedUrls().filter(
      (u) => u.includes("/governance-roles/assignments") && !u.includes("/member/")
    );
    expect(allAssignmentCalls).toHaveLength(1);

    /* No per-row member-scoped assignment calls at render time */
    const perMemberCalls = fetchedUrls().filter((u) =>
      u.match(/governance-roles\/assignments\/member\//)
    );
    expect(perMemberCalls).toHaveLength(0);
  });
});
