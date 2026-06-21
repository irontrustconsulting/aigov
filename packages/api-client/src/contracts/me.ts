/** app/schemas/governance.py MeRead — server-authoritative roles (D-24),
 * never token claims. WI-10's role-aware render pass reads this. */
export interface GovernanceRoleRead {
  id: string;
  key: string;
  name: string;
  description: string | null;
  line_of_defence: number;
}

export interface MeRead {
  membership_id: string;
  tenant_id: string;
  role: string;
  email: string | null;
  name: string | null;
  governance_roles: GovernanceRoleRead[];
}
