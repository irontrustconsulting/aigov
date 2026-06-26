import { type ReactNode } from "react";

export interface PageScaffoldProps {
  children: ReactNode;
  /** FE-21 ALTER: 'default' keeps max-w-4xl (all current consumers unchanged). */
  width?: "default" | "wide" | "full";
}

const WIDTH_CLASS: Record<NonNullable<PageScaffoldProps["width"]>, string> = {
  default: "max-w-4xl",
  wide: "max-w-6xl",
  full: "",
};

/** PageScaffold — content width, section rhythm, and padding (FE-21).
 *  Composed inside AppShell's <main>. New surfaces use this; existing surfaces
 *  are updated in per-surface composition passes (Appendix C register). */
export function PageScaffold({ children, width = "default" }: PageScaffoldProps) {
  return (
    <div className={`mx-auto ${WIDTH_CLASS[width]} space-y-8 px-6 py-8`}>{children}</div>
  );
}
