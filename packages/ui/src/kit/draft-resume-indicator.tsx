import { ChevronRight } from "lucide-react";

export interface DraftResumeIndicatorProps {
  productLabel: string | null;
  href: string;
}

export function DraftResumeIndicator({ productLabel, href }: DraftResumeIndicatorProps) {
  return (
    <section
      aria-label="draft-resume"
      className="rounded-lg border border-hairline bg-paper p-4 flex items-center justify-between gap-4"
      style={{ boxShadow: "var(--elevation-raised)" }}
    >
      <div>
        <p className="text-sm font-medium text-ink">You have a registration in progress.</p>
        <p className="text-sm text-ink-muted mt-0.5">
          {productLabel ?? "Untitled registration"}
        </p>
      </div>
      <a
        href={href}
        className="inline-flex items-center gap-1 text-sm font-medium text-brand hover:underline shrink-0"
      >
        Resume
        <ChevronRight className="h-4 w-4" aria-hidden="true" />
      </a>
    </section>
  );
}
