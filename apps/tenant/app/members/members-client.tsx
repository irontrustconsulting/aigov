"use client";

import { PageScaffold, PageHeader } from "@irontrust/ui";
import { useMe } from "@/lib/intake";
import { MembersList } from "./_components/members-list";

/**
 * Root-branch on me.role === "admin" (DF-F9-3 / P3 literal casing).
 * Non-admin: not-authorised treatment; zero GET /v1/members issued.
 * Admin: members surface.
 */
export function MembersClient() {
  const me = useMe();

  if (me.isLoading) {
    return (
      <PageScaffold>
        <PageHeader title="Members" />
        <p className="text-ink-muted text-sm">Loading…</p>
      </PageScaffold>
    );
  }

  if (me.isError || !me.data) {
    return (
      <PageScaffold>
        <PageHeader title="Members" />
        <p className="text-danger text-sm" role="alert">Could not load your role.</p>
      </PageScaffold>
    );
  }

  if (me.data.role !== "admin") {
    return (
      <PageScaffold>
        <PageHeader title="Members" />
        <p className="text-ink-muted text-sm" role="status" data-testid="not-authorised">
          Member management is available to administrators only.
        </p>
      </PageScaffold>
    );
  }

  return (
    <PageScaffold>
      <PageHeader title="Members" subtitle="Manage team members and governance role assignments." />
      <MembersList actingMembershipId={me.data.membership_id} />
    </PageScaffold>
  );
}
