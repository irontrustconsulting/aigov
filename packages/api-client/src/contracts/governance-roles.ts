/** Governance role assignment contracts — mirrors app/schemas/governance.py */
import type { GovernanceRoleRead } from "./me";

export interface GovernanceRoleConflictRead {
  id: string;
  role_a_id: string;
  role_b_id: string;
}

export interface GovernanceCatalogueRead {
  roles: GovernanceRoleRead[];
  conflicts: GovernanceRoleConflictRead[];
}

export interface GovernanceRoleAssignmentCreate {
  membership_id: string;
  governance_role_id: string;
}

export interface GovernanceRoleAssignmentRead {
  id: string;
  tenant_id: string;
  membership_id: string;
  governance_role_id: string;
  granted_by_membership_id: string | null;
  granted_at: string;
}
