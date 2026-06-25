import { type ReactNode } from "react";

export interface PageScaffoldProps {
  children: ReactNode;
}

/** PageScaffold — content width, section rhythm, and padding (FE-21).
 *  Composed inside AppShell's <main>. New surfaces use this; existing surfaces
 *  are updated in per-surface composition passes (Appendix C register). */
export function PageScaffold({ children }: PageScaffoldProps) {
  return (
    <div className="mx-auto max-w-4xl space-y-8 px-6 py-8">{children}</div>
  );
}
