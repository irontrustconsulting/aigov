"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { Sidebar, type SidebarNavItem } from "@irontrust/ui";
import { api } from "@/lib/api";
import type { MeRead } from "@irontrust/api-client";

const PORTFOLIO_ENTRY: Omit<SidebarNavItem, "isActive"> = {
  href: "/dashboard",
  label: "Portfolio",
};

const REVIEW_QUEUE_ENTRY: Omit<SidebarNavItem, "isActive"> = {
  href: "/review-queue",
  label: "Review queue",
};

const CLEARANCES_ENTRY: Omit<SidebarNavItem, "isActive"> = {
  href: "/clearances",
  label: "Clearances",
};

const EVIDENCE_ENTRY: Omit<SidebarNavItem, "isActive"> = {
  href: "/evidence",
  label: "Evidence",
};

const AUDIT_ENTRY: Omit<SidebarNavItem, "isActive"> = {
  href: "/audit",
  label: "Audit",
};

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

  const governanceRoleKeys = new Set(me?.governance_roles.map((r) => r.key) ?? []);

  /* DF-CLR-10/11 / INV-91: Review queue is hidden from non-reviewers (SoD —
   * reviewer/authoriser conflict, D-4). Clearances is navigable by any
   * governance role (reading clearance status breaches no SoD; the
   * set-clearance act is gated inside the surface, INV-86). Evidence,
   * Audit, Portfolio carry no SoD constraint and stay unconditional. */
  const baseItems = [
    PORTFOLIO_ENTRY,
    ...(governanceRoleKeys.has("reviewer") ? [REVIEW_QUEUE_ENTRY] : []),
    ...(governanceRoleKeys.size > 0 ? [CLEARANCES_ENTRY] : []),
    EVIDENCE_ENTRY,
    AUDIT_ENTRY,
    ...(me?.role === "admin" ? [MEMBERS_ENTRY] : []),
  ];

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
