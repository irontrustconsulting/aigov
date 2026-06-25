"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import type {
  MemberCreated,
  GovernanceRoleAssignmentRead,
} from "@irontrust/api-client";
import { api } from "@/lib/api";
import { membersKeys } from "./query-keys";

/** POST /v1/members — admin invites a new member; invalidates the list on success. */
export function useInviteMember() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ email, name }: { email: string; name: string }) =>
      api.post<MemberCreated>("/v1/members", { email, name }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: membersKeys.list() });
    },
  });
}

/** POST /governance-roles/assignments — assign a role to a member. */
export function useAssignRole() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      membershipId,
      governanceRoleId,
    }: {
      membershipId: string;
      governanceRoleId: string;
    }) =>
      api.post<GovernanceRoleAssignmentRead>("/v1/governance-roles/assignments", {
        membership_id: membershipId,
        governance_role_id: governanceRoleId,
      }),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({
        queryKey: membersKeys.assignments(variables.membershipId),
      });
      queryClient.invalidateQueries({ queryKey: membersKeys.allAssignments() });
    },
  });
}

/** DELETE /governance-roles/assignments/{assignmentId} — revoke a role. */
export function useRevokeRole() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      assignmentId,
    }: {
      assignmentId: string;
      membershipId: string;
    }) => api.delete(`/v1/governance-roles/assignments/${assignmentId}`),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({
        queryKey: membersKeys.assignments(variables.membershipId),
      });
      queryClient.invalidateQueries({ queryKey: membersKeys.allAssignments() });
    },
  });
}
