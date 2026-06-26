import { type ReactNode } from "react";

export interface SectionGroupProps {
  title: string;
  children: ReactNode;
  sunken?: boolean;
}

/**
 * FE-27: Section grouping with petrol marker + label + optional sunken
 * sub-panel + divider. Petrol on marker and label only (D-57).
 */
export function SectionGroup({ title, children, sunken = false }: SectionGroupProps) {
  return (
    <div className="pb-6 border-b border-hairline last:border-b-0 last:pb-0">
      <div className="flex items-center gap-3 mb-4">
        <div className="w-0.5 self-stretch bg-brand rounded-full" aria-hidden="true" />
        <span className="text-xs font-semibold uppercase tracking-wider text-brand">
          {title}
        </span>
      </div>
      {sunken ? (
        <div
          className="rounded-lg p-4"
          style={{ backgroundColor: "var(--color-surface-sunken)" }}
        >
          {children}
        </div>
      ) : (
        children
      )}
    </div>
  );
}
