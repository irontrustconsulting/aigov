import type { ReactNode } from "react";

export type QueueRowDensity = "comfortable" | "compact";

/** A clickable row for a review/approval queue surface; styling only —
 * SoD-visible action controls inside it are composed via SodAction (FE-8). */
export function QueueRow({
  onClick,
  children,
  density = "comfortable",
}: {
  onClick?: () => void;
  children: ReactNode;
  density?: QueueRowDensity;
}) {
  return (
    <div
      onClick={onClick}
      role={onClick ? "button" : undefined}
      tabIndex={onClick ? 0 : undefined}
      className={[
        "border-hairline hover:bg-surface-sunken flex items-center justify-between border-b text-ink",
        density === "comfortable" ? "px-4 py-3 text-sm" : "px-3 py-1.5 text-xs",
      ].join(" ")}
    >
      {children}
    </div>
  );
}
