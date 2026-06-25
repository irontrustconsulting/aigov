export const membersKeys = {
  list: () => ["members"] as const,
  assignments: (membershipId: string) => ["member-assignments", membershipId] as const,
  catalogue: () => ["governance-catalogue"] as const,
  allAssignments: () => ["members-all-assignments"] as const,
} as const;
