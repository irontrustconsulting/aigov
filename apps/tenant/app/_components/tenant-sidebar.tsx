"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { Sidebar, type SidebarNavItem } from "@irontrust/ui";
import { api } from "@/lib/api";
import type { MeRead } from "@irontrust/api-client";

const BASE_NAV: Omit<SidebarNavItem, "isActive">[] = [
  { href: "/dashboard", label: "Portfolio" },
  { href: "/review-queue", label: "Review queue" },
  { href: "/evidence", label: "Evidence" },
  { href: "/audit", label: "Audit" },
];

function AccountBlock() {
  const { data } = useQuery({
    queryKey: ["me"],
    queryFn: () => api.get<MeRead>("/v1/me"),
    staleTime: 5 * 60 * 1000,
  });

  const displayName = data?.name ?? data?.email ?? null;

  return (
    <div className="space-y-1 px-1 py-1">
      {displayName && (
        <p className="truncate text-xs font-medium text-ink">{displayName}</p>
      )}
      {/* NOTE: tenant name absent from MeRead (tenant_id only); flagged C0-PREFLIGHT.md. */}
      <a href="/api/auth/logout" className="block text-xs text-ink-muted hover:text-ink">
        Sign out
      </a>
    </div>
  );
}

export function TenantSidebar() {
  const pathname = usePathname();

  const navItems: SidebarNavItem[] = BASE_NAV.map((item) => ({
    ...item,
    isActive:
      pathname === item.href ||
      (item.href !== "/" && pathname.startsWith(item.href)),
  }));

  return (
    <Sidebar
      brand={
        <Link href="/dashboard" className="text-sm font-semibold text-ink hover:text-brand">
          IronTrust
        </Link>
      }
      navItems={navItems}
      foot={<AccountBlock />}
    />
  );
}
