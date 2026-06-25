"use client";

import { useEffect, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { AppShell } from "@irontrust/ui";
import { api } from "@/lib/api";
import { OperatorSidebar } from "./_components/operator-sidebar";

interface PlatformMe {
  id: string;
  email: string | null;
  display_name: string | null;
  permissions: string[];
}

export default function ConsoleLayout({ children }: { children: ReactNode }) {
  const meQuery = useQuery({
    queryKey: ["platform-me"],
    queryFn: () => api.get<PlatformMe>("/platform/me"),
  });

  useEffect(() => {
    if (meQuery.isError) window.location.href = "/api/auth/login";
  }, [meQuery.isError]);

  const permissions = meQuery.data?.permissions ?? [];

  return (
    <AppShell
      sidebar={
        <OperatorSidebar
          permissions={permissions}
          displayName={meQuery.data?.display_name}
          email={meQuery.data?.email}
        />
      }
    >
      {children}
    </AppShell>
  );
}
