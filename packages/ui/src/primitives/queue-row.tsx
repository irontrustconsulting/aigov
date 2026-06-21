import type { ReactNode } from "react";

/** A clickable row for a review/approval queue surface; styling only —
 * SoD-visible action controls inside it are composed via SodAction (FE-8). */
export function QueueRow({ onClick, children }: { onClick?: () => void; children: ReactNode }) {
  return (
    <div
      onClick={onClick}
      role={onClick ? "button" : undefined}
      tabIndex={onClick ? 0 : undefined}
      className="border-border hover:bg-surface flex items-center justify-between border-b px-3 py-2 text-sm"
    >
      {children}
    </div>
  );
}
