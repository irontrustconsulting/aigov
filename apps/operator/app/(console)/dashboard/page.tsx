"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

interface PlatformMe {
  id: string;
  email: string | null;
  display_name: string | null;
  permissions: string[];
}

/**
 * W7a smoke surface — not a feature surface. Proves login -> BFF holds
 * token -> bearer forwarded -> API returns caller-scoped data -> render, via
 * GET /platform/me (D-39).
 */
export default function DashboardPage() {
  const me = useQuery({
    queryKey: ["platform-me"],
    queryFn: () => api.get<PlatformMe>("/platform/me"),
  });

  if (me.isLoading) return <p>Loading…</p>;
  if (me.isError || !me.data) return <p role="alert">Failed to load identity.</p>;

  return (
    <main>
      <h1>Signed in</h1>
      <dl>
        <dt>Email</dt>
        <dd>{me.data.email}</dd>
        <dt>Permissions</dt>
        <dd>{me.data.permissions.join(", ")}</dd>
      </dl>
    </main>
  );
}
