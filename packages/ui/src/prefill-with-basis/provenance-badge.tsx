/** The fixed 4-value provenance vocabulary (PAT-8, INV-13) — never a 5th
 * value, never client-set. The server is the only source of this value. */
export type Provenance = "AI_SUGGESTED" | "CATALOGUE_CURATED" | "USER_CONFIRMED" | "USER_AMENDED";

const LABELS: Record<Provenance, string> = {
  AI_SUGGESTED: "AI suggested",
  CATALOGUE_CURATED: "Catalogue",
  USER_CONFIRMED: "Confirmed",
  USER_AMENDED: "Amended",
};

const CLASSES: Record<Provenance, string> = {
  AI_SUGGESTED: "bg-surface text-text-muted border-border",
  CATALOGUE_CURATED: "bg-surface text-text-muted border-border",
  USER_CONFIRMED: "bg-success text-bg border-transparent",
  USER_AMENDED: "bg-warning text-bg border-transparent",
};

export function ProvenanceBadge({ provenance }: { provenance: Provenance }) {
  return (
    <span
      className={[
        "inline-flex items-center rounded-sm border px-2 py-1 text-xs font-medium",
        CLASSES[provenance],
      ].join(" ")}
    >
      {LABELS[provenance]}
    </span>
  );
}
