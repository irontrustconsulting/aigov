"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

interface PlatformWhoAmI {
  id: string;
  cognito_sub: string;
  email: string | null;
  display_name: string | null;
  permissions: string[];
}

/**
 * W7a smoke surface — not a feature surface. Proves login -> BFF holds
 * token -> bearer forwarded -> API returns caller-scoped data -> render, via
 * GET /platform/whoami. That route is gated by require_permission
 * ("tenant:provision"), not a bare identity read (its own docstring calls
 * it a verification aid) — used as-is for F0 per the sprint's W7a decision;
 * the genesis-operator test fixture is granted that permission regardless.
 */
export default function DashboardPage() {
  const whoami = useQuery({
    queryKey: ["platform-whoami"],
    queryFn: () => api.get<PlatformWhoAmI>("/platform/whoami"),
  });

  if (whoami.isLoading) return <p>Loading…</p>;
  if (whoami.isError || !whoami.data) return <p role="alert">Failed to load identity.</p>;

  return (
    <main>
      <h1>Signed in</h1>
      <dl>
        <dt>Email</dt>
        <dd>{whoami.data.email}</dd>
        <dt>Permissions</dt>
        <dd>{whoami.data.permissions.join(", ")}</dd>
      </dl>
    </main>
  );
}
