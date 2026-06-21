/** The fixed 4-value provenance vocabulary (PAT-8, INV-13) — never a 5th
 * value, never client-set. The server is the only source of this value.
 * Lowercase wire values — Pydantic serialises `ProvenanceConfidence` (a
 * `str, enum.Enum`) by VALUE, not by member name (confirmed against
 * tests/test_system_intake.py: `f["provenance"] == "catalogue_curated"`) —
 * the same footgun the sprint's §0.5 flags for tier/status enums. */
export type Provenance = "ai_suggested" | "catalogue_curated" | "user_confirmed" | "user_amended";

const LABELS: Record<Provenance, string> = {
  ai_suggested: "AI suggested",
  catalogue_curated: "Catalogue",
  user_confirmed: "Confirmed",
  user_amended: "Amended",
};

const CLASSES: Record<Provenance, string> = {
  ai_suggested: "bg-surface text-text-muted border-border",
  catalogue_curated: "bg-surface text-text-muted border-border",
  user_confirmed: "bg-success text-bg border-transparent",
  user_amended: "bg-warning text-bg border-transparent",
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
