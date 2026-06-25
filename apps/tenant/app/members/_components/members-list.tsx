"use client";

import { useState } from "react";
import {
  DataTable,
  DataTableHeader,
  DataTableBody,
  TableRow,
  TableCell,
  TableHeaderCell,
  Skeleton,
  ErrorState,
  FirstRunPanel,
  Button,
} from "@irontrust/ui";
import type { MemberRead } from "@irontrust/api-client";
import { useMembers, useGovernanceCatalogue, useAllAssignments } from "@/lib/members";
import { RolePanel } from "./role-panel";
import { InviteDialog } from "./invite-dialog";

/**
 * Accept-status chip — neutral non-semantic chrome (FE-16 / WI-2).
 * No --verdict-* token. pending = outline; accepted = muted fill.
 */
function AcceptChip({ status }: { status: "pending" | "accepted" }) {
  if (status === "accepted") {
    return (
      <span
        className="bg-surface-sunken text-ink rounded-sm px-2 py-0.5 text-xs"
        data-accept-status="accepted"
      >
        Accepted
      </span>
    );
  }
  return (
    <span
      className="border-hairline text-ink-muted rounded-sm border px-2 py-0.5 text-xs"
      data-accept-status="pending"
    >
      Pending
    </span>
  );
}

interface MembersListProps {
  actingMembershipId: string;
}

export function MembersList({ actingMembershipId }: MembersListProps) {
  const membersQuery = useMembers();
  const catalogueQuery = useGovernanceCatalogue();
  const allAssignmentsQuery = useAllAssignments();

  const [inviteOpen, setInviteOpen] = useState(false);
  const [selectedMember, setSelectedMember] = useState<MemberRead | null>(null);

  if (membersQuery.isLoading) {
    return <Skeleton lines={4} />;
  }

  if (membersQuery.isError) {
    return (
      <ErrorState
        message="Could not load members."
        onRetry={() => membersQuery.refetch()}
      />
    );
  }

  const members = membersQuery.data?.items ?? [];

  if (members.length <= 1) {
    return (
      <>
        <FirstRunPanel
          heading="No other members yet"
          body="Invite team members to assign governance roles and enable the multi-person review-to-authorise loop."
          action={
            <Button onClick={() => setInviteOpen(true)}>Invite member</Button>
          }
        />
        <InviteDialog open={inviteOpen} onClose={() => setInviteOpen(false)} />
      </>
    );
  }

  const catalogue = catalogueQuery.data;

  /* Build a roles-held map from the single tenant-wide fetch (WI-6, no N+1). */
  const rolesByMembership = new Map<string, string[]>();
  if (catalogue && allAssignmentsQuery.data) {
    const roleNameById = new Map(catalogue.roles.map((r) => [r.id, r.name]));
    for (const a of allAssignmentsQuery.data) {
      const names = rolesByMembership.get(a.membership_id) ?? [];
      const name = roleNameById.get(a.governance_role_id);
      if (name) names.push(name);
      rolesByMembership.set(a.membership_id, names);
    }
  }

  return (
    <>
      <div className="flex items-center justify-between">
        <p className="text-ink-muted text-sm">{members.length} member{members.length !== 1 ? "s" : ""}</p>
        <Button onClick={() => setInviteOpen(true)}>Invite member</Button>
      </div>

      <DataTable>
        <DataTableHeader>
          <TableHeaderCell>Name</TableHeaderCell>
          <TableHeaderCell>Email</TableHeaderCell>
          <TableHeaderCell>Role</TableHeaderCell>
          <TableHeaderCell>Status</TableHeaderCell>
          <TableHeaderCell>Governance roles</TableHeaderCell>
          <TableHeaderCell>{/* actions */}</TableHeaderCell>
        </DataTableHeader>
        <DataTableBody>
          {members.map((member) => {
            const heldNames = rolesByMembership.get(member.membership_id) ?? [];
            return (
              <TableRow key={member.membership_id}>
                <TableCell>{member.name ?? "—"}</TableCell>
                <TableCell>{member.email}</TableCell>
                <TableCell className="capitalize">{member.role}</TableCell>
                <TableCell>
                  <AcceptChip status={member.status} />
                </TableCell>
                <TableCell>
                  {heldNames.length > 0
                    ? heldNames.join(", ")
                    : <span className="text-ink-muted text-xs">None</span>}
                </TableCell>
                <TableCell>
                  <Button
                    variant="ghost"
                    onClick={() => setSelectedMember(member)}
                    aria-label={`Manage roles for ${member.name ?? member.email}`}
                  >
                    Manage roles
                  </Button>
                </TableCell>
              </TableRow>
            );
          })}
        </DataTableBody>
      </DataTable>

      <InviteDialog open={inviteOpen} onClose={() => setInviteOpen(false)} />

      {selectedMember && (
        <RolePanel
          member={selectedMember}
          actingMembershipId={actingMembershipId}
          open={Boolean(selectedMember)}
          onClose={() => setSelectedMember(null)}
        />
      )}
    </>
  );
}
