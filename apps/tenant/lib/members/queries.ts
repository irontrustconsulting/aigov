"use client";

import { useQuery } from "@tanstack/react-query";
import type {
  MemberListResponse,
  GovernanceCatalogueRead,
  GovernanceRoleAssignmentRead,
} from "@irontrust/api-client";
import { api } from "@/lib/api";
import { membersKeys } from "./query-keys";

/** GET /v1/members — admin-only keyset list with Cognito accept status. */
export function useMembers() {
  return useQuery({
    queryKey: membersKeys.list(),
    queryFn: () => api.get<MemberListResponse>("/v1/members"),
    staleTime: 0,
  });
}

/**
 * GET /governance-roles/assignments/member/{membershipId}
 * Per-member held grants. Pass enabled=false until the panel opens (WI-4).
 */
export function useMemberAssignments(membershipId: string, enabled: boolean) {
  return useQuery({
    queryKey: membersKeys.assignments(membershipId),
    queryFn: () =>
      api.get<GovernanceRoleAssignmentRead[]>(
        `/v1/governance-roles/assignments/member/${membershipId}`
      ),
    enabled,
    staleTime: 0,
  });
}

/** GET /governance-roles/catalogue — 5 canonical roles + full conflict matrix. */
export function useGovernanceCatalogue() {
  return useQuery({
    queryKey: membersKeys.catalogue(),
    queryFn: () => api.get<GovernanceCatalogueRead>("/v1/governance-roles/catalogue"),
    staleTime: 5 * 60 * 1000,
  });
}

/**
 * GET /governance-roles/assignments — tenant-wide; no membership filter.
 * P5 confirmed present. Used for the roles-held list column (WI-6):
 * single fetch, group by membership_id, no N+1.
 */
export function useAllAssignments() {
  return useQuery({
    queryKey: membersKeys.allAssignments(),
    queryFn: () =>
      api.get<GovernanceRoleAssignmentRead[]>("/v1/governance-roles/assignments"),
    staleTime: 0,
  });
}
