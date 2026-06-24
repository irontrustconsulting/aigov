"use client";

import { useEffect, type ReactNode } from "react";
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
const PERM_OPERATOR_CREATE = "operator:create";

const UNBUILT: { label: string }[] = [
  { label: "Catalogue Curation" },
  { label: "Curation Inbox" },
];

export default function ConsoleLayout({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const meQuery = useQuery({
    queryKey: ["platform-me"],
    queryFn: () => api.get<PlatformMe>("/platform/me"),
  });

  useEffect(() => {
    if (meQuery.isError) window.location.href = "/api/auth/login";
  }, [meQuery.isError]);

  const permissions = meQuery.data?.permissions ?? [];

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

          <RequirePermission permission={PERM_OPERATOR_CREATE} permissions={permissions}>
            <li>
              <Link
                href="/operators"
                aria-current={pathname.startsWith("/operators") ? "page" : undefined}
              >
                RBAC Management
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
