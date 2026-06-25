"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Sidebar } from "@irontrust/ui";
import { RequirePermission } from "@/components/require-permission";

const PERM_PROVISION = "tenant:provision";
const PERM_OPERATOR_CREATE = "operator:create";

const UNBUILT: string[] = ["Catalogue Curation", "Curation Inbox"];

interface OperatorSidebarProps {
  permissions: string[];
  displayName?: string | null;
  email?: string | null;
}

function OperatorFoot({
  displayName,
  email,
}: {
  displayName?: string | null;
  email?: string | null;
}) {
  const label = displayName ?? email ?? null;
  return (
    <div className="space-y-1 px-1 py-1">
      {label && (
        <p className="truncate text-xs font-medium text-surface">{label}</p>
      )}
      <a href="/api/auth/logout" className="block text-xs text-surface opacity-70">
        Sign out
      </a>
    </div>
  );
}

export function OperatorSidebar({
  permissions,
  displayName,
  email,
}: OperatorSidebarProps) {
  const pathname = usePathname();

  // NOTE: operator sidebar visual target (rail accent variant) is pending from
  // designer (flagged per INV-68 / sprint WI-2). Rail token per design doc §4a (INV-60).
  const nav = (
    <nav aria-label="Operator console navigation">
      <ul className="space-y-0.5" role="list">
        <RequirePermission permission={PERM_PROVISION} permissions={permissions}>
          <li>
            <Link
              href="/provisioning"
              aria-current={pathname.startsWith("/provisioning") ? "page" : undefined}
              className="block rounded-md px-3 py-2 text-sm font-medium text-surface transition-colors hover:bg-white/10"
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
              className="block rounded-md px-3 py-2 text-sm font-medium text-surface transition-colors hover:bg-white/10"
            >
              RBAC Management
            </Link>
          </li>
        </RequirePermission>

        {UNBUILT.map((label) => (
          <li key={label} aria-disabled="true">
            <span
              className="block cursor-not-allowed rounded-md px-3 py-2 text-sm text-surface opacity-40"
              title="Not yet available"
            >
              {label}
            </span>
          </li>
        ))}
      </ul>
    </nav>
  );

  return (
    <Sidebar
      brand={
        <Link href="/" className="text-sm font-semibold text-surface">
          IronTrust
        </Link>
      }
      nav={nav}
      railBg="var(--chrome-rail-bg)"
      foot={<OperatorFoot displayName={displayName} email={email} />}
    />
  );
}
