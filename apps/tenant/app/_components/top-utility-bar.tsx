"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { MeRead } from "@irontrust/api-client";

export function TopUtilityBar() {
  const { data } = useQuery({
    queryKey: ["me"],
    queryFn: () => api.get<MeRead>("/v1/me"),
    staleTime: 5 * 60 * 1000,
  });

  const displayName = data?.name ?? data?.email ?? null;

  const handleSignOut = async () => {
    const res = await fetch("/api/auth/logout", { method: "POST" });
    const { redirectTo } = (await res.json()) as { redirectTo: string };
    window.location.href = redirectTo;
  };

  return (
    <div className="flex h-10 shrink-0 items-center justify-end gap-4 border-b border-hairline bg-surface px-4">
      {displayName && (
        <span className="truncate text-xs text-ink-muted">{displayName}</span>
      )}
      <button
        type="button"
        onClick={handleSignOut}
        className="text-xs text-ink-muted hover:text-ink"
      >
        Sign out
      </button>
    </div>
  );
}
