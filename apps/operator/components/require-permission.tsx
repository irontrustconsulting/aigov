import type { ReactNode } from "react";

interface RequirePermissionProps {
  permission: string;
  permissions: string[];
  children: ReactNode;
}

/**
 * FE-13: operator-console permission-aware render gate.
 *
 * Renders children only when the operator holds the named permission.
 * Absent when not held — never disabled. Presentational only; the backend
 * require_permission() guard is the authz authority (INV-8, D-24).
 */
export function RequirePermission({
  permission,
  permissions,
  children,
}: RequirePermissionProps) {
  if (!permissions.includes(permission)) return null;
  return <>{children}</>;
}
