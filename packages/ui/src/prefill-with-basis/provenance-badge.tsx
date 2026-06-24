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

/* FE-15: provenance hue lives on the border only; label is always --ink
 * (text AA not required — hue only needs the 3:1 graphical floor; V-7). */
export const PROV_BORDER_COLOR: Record<Provenance, string> = {
  ai_suggested: "var(--prov-ai-suggested)",
  catalogue_curated: "var(--prov-catalogue-curated)",
  user_confirmed: "var(--prov-user-confirmed)",
  user_amended: "var(--prov-user-amended)",
};

export function ProvenanceBadge({ provenance }: { provenance: Provenance }) {
  const isDashed = provenance === "ai_suggested";
  return (
    <span
      className={[
        "inline-flex items-center rounded-sm border px-2 py-1 text-xs font-medium bg-surface text-ink",
        isDashed ? "border-dashed" : "border-solid",
      ].join(" ")}
      style={{ borderColor: PROV_BORDER_COLOR[provenance] }}
    >
      {LABELS[provenance]}
    </span>
  );
}
