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

const MEMBERS_ENTRY: Omit<SidebarNavItem, "isActive"> = {
  href: "/members",
  label: "Members",
};

function TenantFoot() {
  const { data } = useQuery({
    queryKey: ["me"],
    queryFn: () => api.get<MeRead>("/v1/me"),
    staleTime: 5 * 60 * 1000,
  });

  return (
    <div className="px-1 py-1">
      {data?.tenant_name && (
        <p className="truncate text-xs font-medium text-ink">{data.tenant_name}</p>
      )}
    </div>
  );
}

export function TenantSidebar() {
  const pathname = usePathname();
  const { data: me } = useQuery({
    queryKey: ["me"],
    queryFn: () => api.get<MeRead>("/v1/me"),
    staleTime: 5 * 60 * 1000,
  });

  const baseItems = me?.role === "admin"
    ? [...BASE_NAV, MEMBERS_ENTRY]
    : BASE_NAV;

  const navItems: SidebarNavItem[] = baseItems.map((item) => ({
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
      foot={<TenantFoot />}
    />
  );
}
