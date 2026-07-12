"use client";

import { PageScaffold, PageHeader, EmptyState } from "@irontrust/ui";
import { useMe } from "@/lib/intake";
import { ClearanceQueueList } from "./_components/clearance-queue-list";

/**
 * Root-branch on governance_roles (DF-CLR-17): zero governance roles (the
 * admin case) gets the empty-state with no GET /clearance-queue issued; any
 * governance role gets the read-only queue; authoriser additionally gets
 * the set-clearance action, gated per-row inside ClearanceQueueList.
 */
export function ClearancesClient() {
  const me = useMe();

  if (me.isLoading) {
    return (
      <PageScaffold>
        <PageHeader title="Clearances" />
        <p className="text-ink-muted text-sm">Loading…</p>
      </PageScaffold>
    );
  }

  if (me.isError || !me.data) {
    return (
      <PageScaffold>
        <PageHeader title="Clearances" />
        <p className="text-danger text-sm" role="alert">Could not load your role.</p>
      </PageScaffold>
    );
  }

  if (me.data.governance_roles.length === 0) {
    return (
      <PageScaffold>
        <PageHeader title="Clearances" />
        <EmptyState message="Clearance status is visible to callers holding a governance role." />
      </PageScaffold>
    );
  }

  const isAuthoriser = me.data.governance_roles.some((r) => r.key === "authoriser");

  return (
    <PageScaffold>
      <PageHeader
        title="Clearances"
        subtitle="Vendor and product clearance status for every use case parked at these gates."
      />
      <ClearanceQueueList isAuthoriser={isAuthoriser} />
    </PageScaffold>
  );
}
