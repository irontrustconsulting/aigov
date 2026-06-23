"use client";

import type { ReactNode } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { RequirePermission } from "@/components/require-permission";

interface PlatformMe {
  id: string;
  email: string | null;
  display_name: string | null;
  permissions: string[];
}

const PERM_PROVISION = "tenant:provision";

const UNBUILT: { label: string }[] = [
  { label: "RBAC Management" },
  { label: "Catalogue Curation" },
  { label: "Curation Inbox" },
];

export default function ConsoleLayout({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const { data: me } = useQuery({
    queryKey: ["platform-me"],
    queryFn: () => api.get<PlatformMe>("/platform/me"),
  });

  const permissions = me?.permissions ?? [];

  return (
    <div className="console-layout">
      <nav aria-label="Operator console navigation">
        <ul>
          <RequirePermission permission={PERM_PROVISION} permissions={permissions}>
            <li>
              <Link
                href="/provisioning"
                aria-current={pathname.startsWith("/provisioning") ? "page" : undefined}
              >
                Provisioning
              </Link>
            </li>
          </RequirePermission>

          {UNBUILT.map(({ label }) => (
            <li key={label} aria-disabled="true">
              <span title="Not yet available">{label}</span>
            </li>
          ))}
        </ul>
      </nav>

      <main>{children}</main>
    </div>
  );
}
