import { cloneElement, isValidElement, type ReactElement, type ReactNode } from "react";

export interface SodActionProps {
  /** Structural — the server says the caller is barred from this act by
   * separation of duties (e.g. INV-28: a reviewer cannot review their own
   * submission). Renders nothing at all, not disabled. */
  barred: boolean;
  /** Transient — a non-SoD reason the action can't be taken right now (wrong
   * lifecycle state, stale lock). Renders the child disabled with the
   * reason attached. Ignored when `barred` is true. */
  blockedReason?: string | null;
  children: ReactNode;
}

/**
 * FE-8: the visual correlate of act-SoD. Both `barred` and `blockedReason`
 * must be server-derived booleans/strings passed in by the calling surface
 * from a live-state read (never computed client-side) — this component does
 * no authz logic, only branches on what it's told.
 *
 * Presentational only (D-4, INV-7, INV-28, D-24): the backend remains the
 * SoD/authz authority. A control this component omits or disables is still
 * rejected server-side if invoked some other way — the UI is never the
 * enforcement locus.
 */
export function SodAction({ barred, blockedReason, children }: SodActionProps) {
  if (barred) return null;

  if (blockedReason && isValidElement(children)) {
    const element = children as ReactElement<{
      disabled?: boolean;
      "aria-describedby"?: string;
      title?: string;
    }>;
    return (
      <span>
        {cloneElement(element, {
          disabled: true,
          "aria-describedby": "sod-blocked-reason",
          title: blockedReason,
        })}
        <span id="sod-blocked-reason" role="note">
          {blockedReason}
        </span>
      </span>
    );
  }

  return <>{children}</>;
}
