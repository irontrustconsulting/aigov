"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

interface WhoAmI {
  sub: string;
  email: string | null;
  name: string | null;
  tenant_id: string;
  role: string | null;
}

interface GovernanceRole {
  id: string;
  key: string;
  name: string;
  description: string | null;
  line_of_defence: number;
}

interface Me {
  membership_id: string;
  tenant_id: string;
  role: string;
  email: string | null;
  name: string | null;
  governance_roles: GovernanceRole[];
}

// Second/third-line roles — assurance-face affordances are gated on holding
// at least one of these (UX-5, D-24: from the server-authoritative role set,
// never a token claim).
const ASSURANCE_ROLE_KEYS = new Set(["reviewer", "authoriser", "auditor"]);

/**
 * W7a/W7b smoke surface — not a feature surface. Proves login -> BFF holds
 * token -> bearer forwarded -> API returns caller-scoped data -> render
 * (W7a, via GET /v1/whoami), then extends that with a role-aware render
 * sourced from GET /v1/me (W7b).
 */
export default function DashboardPage() {
  const whoami = useQuery({
    queryKey: ["whoami"],
    queryFn: () => api.get<WhoAmI>("/v1/whoami"),
  });
  const me = useQuery({
    queryKey: ["me"],
    queryFn: () => api.get<Me>("/v1/me"),
  });

  if (whoami.isLoading || me.isLoading) return <p>Loading…</p>;
  if (whoami.isError || !whoami.data || me.isError || !me.data) {
    return <p role="alert">Failed to load identity.</p>;
  }

  const hasAssuranceRole = me.data.governance_roles.some((r) => ASSURANCE_ROLE_KEYS.has(r.key));

  return (
    <main>
      <h1>Signed in</h1>
      <dl>
        <dt>Email</dt>
        <dd>{whoami.data.email}</dd>
        <dt>Tenant</dt>
        <dd>{whoami.data.tenant_id}</dd>
      </dl>

      <section aria-label="adoption-affordance">Adoption workspace</section>
      {hasAssuranceRole && (
        <section aria-label="assurance-affordance">Assurance workspace</section>
      )}
    </main>
  );
}
