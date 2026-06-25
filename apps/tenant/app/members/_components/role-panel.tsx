"use client";

import { Dialog, Button } from "@irontrust/ui";
import type { MemberRead, GovernanceRoleRead, GovernanceRoleConflictRead } from "@irontrust/api-client";
import { useMemberAssignments, useGovernanceCatalogue } from "@/lib/members";
import { useAssignRole, useRevokeRole } from "@/lib/members";

/**
 * Returns the first held role that conflicts with candidateId per the matrix,
 * or null if the assignment is clear (INV-71).
 * The matrix stores pairs unordered (role_a_id < role_b_id by PK convention).
 */
function getConflict(
  candidateId: string,
  heldIds: string[],
  conflicts: GovernanceRoleConflictRead[],
  roles: GovernanceRoleRead[],
): GovernanceRoleRead | null {
  for (const heldId of heldIds) {
    const isConflict = conflicts.some(
      (c) =>
        (c.role_a_id === candidateId && c.role_b_id === heldId) ||
        (c.role_a_id === heldId && c.role_b_id === candidateId)
    );
    if (isConflict) {
      return roles.find((r) => r.id === heldId) ?? null;
    }
  }
  return null;
}

interface RolePanelProps {
  member: MemberRead;
  actingMembershipId: string;
  open: boolean;
  onClose: () => void;
}

export function RolePanel({ member, actingMembershipId, open, onClose }: RolePanelProps) {
  const isSelf = member.membership_id === actingMembershipId;

  const assignmentsQuery = useMemberAssignments(member.membership_id, open && !isSelf);
  const catalogueQuery = useGovernanceCatalogue();
  const assignRole = useAssignRole();
  const revokeRole = useRevokeRole();

  const catalogue = catalogueQuery.data;
  const assignments = assignmentsQuery.data ?? [];

  const heldRoleIds = assignments.map((a) => a.governance_role_id);

  function handleAssign(roleId: string) {
    assignRole.mutate({ membershipId: member.membership_id, governanceRoleId: roleId });
  }

  function handleRevoke(assignmentId: string) {
    revokeRole.mutate({ assignmentId, membershipId: member.membership_id });
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(o) => { if (!o) onClose(); }}
      title={`Governance roles — ${member.name ?? member.email}`}
    >
      <div className="mt-4 min-w-80 space-y-4">
        {isSelf ? (
          /* Self case (INV-71, B4/A-6): control absent; note only (INV-56). */
          <p className="text-ink-muted text-sm" role="note">
            Governance roles are assigned by another administrator, to preserve separation of duties.
          </p>
        ) : (
          <>
            {(assignmentsQuery.isLoading || catalogueQuery.isLoading) && (
              <p className="text-ink-muted text-sm">Loading…</p>
            )}
            {assignmentsQuery.isError && (
              <p className="text-danger text-sm" role="alert">Could not load role assignments.</p>
            )}
            {catalogue && !assignmentsQuery.isLoading && (
              <ul className="space-y-2" aria-label="governance-roles">
                {catalogue.roles.map((role) => {
                  const assignment = assignments.find((a) => a.governance_role_id === role.id);
                  const isHeld = Boolean(assignment);
                  const conflict = !isHeld
                    ? getConflict(role.id, heldRoleIds, catalogue.conflicts, catalogue.roles)
                    : null;

                  return (
                    <li key={role.id} className="flex items-center justify-between gap-3">
                      <div className="flex-1">
                        <span className="text-sm font-medium text-ink">{role.name}</span>
                        {conflict && (
                          <p className="text-ink-muted text-xs" data-testid="sod-reason">
                            Conflicts with {conflict.name}: separation of duties
                          </p>
                        )}
                      </div>
                      <div>
                        {isHeld ? (
                          <Button
                            variant="ghost"
                            onClick={() => handleRevoke(assignment!.id)}
                            disabled={revokeRole.isPending}
                            aria-label={`Revoke ${role.name}`}
                          >
                            Revoke
                          </Button>
                        ) : (
                          <Button
                            variant="ghost"
                            onClick={() => handleAssign(role.id)}
                            disabled={Boolean(conflict) || assignRole.isPending}
                            aria-label={`Assign ${role.name}`}
                            aria-disabled={Boolean(conflict)}
                          >
                            Assign
                          </Button>
                        )}
                      </div>
                    </li>
                  );
                })}
              </ul>
            )}
            {(assignRole.isError || revokeRole.isError) && (
              <p className="text-danger text-sm" role="alert">
                {(assignRole.error as Error)?.message ??
                  (revokeRole.error as Error)?.message ??
                  "Operation failed."}
              </p>
            )}
          </>
        )}
        <div className="flex justify-end pt-2">
          <Button variant="ghost" onClick={onClose}>Close</Button>
        </div>
      </div>
    </Dialog>
  );
}
