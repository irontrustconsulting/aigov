/**
 * FE-16: VerdictChip — maps live enum members to one of six meaning-class
 * verdict tones. The chip label carries the specific member; the tone carries
 * the meaning-class. One tone family serves assessment_status,
 * lifecycle_state, classification_status, coverage_status, approval_status,
 * and eu_ai_act_tier (V-5 confirmed exhaustive).
 *
 * Orthogonality: the verdict channel never borrows a provenance hue and vice
 * versa. Where a shared hue appears (--brand in court + progress; --verdict-
 * attention in severity medium), the component form disambiguates.
 *
 * eu_ai_act_tier ESCALATION NOTE (V-5): HIGH/LIMITED/MINIMAL are not named
 * in design doc §2.2; implementation tones (HIGH→attention, LIMITED→neutral,
 * MINIMAL→neutral) are flagged for Herbert to confirm at V1.
 */

export type VerdictTone =
  | "neutral"
  | "progress"
  | "positive"
  | "attention"
  | "halt"
  | "terminal";

/** All live enum members mapped to verdict tones (V-5 exhaustive check). */
const TONE_MAP: Record<string, VerdictTone> = {
  /* assessment_status */
  DRAFT: "neutral",
  IN_REVIEW: "progress",
  APPROVED: "positive",
  NEEDS_REFRESH: "attention",

  /* lifecycle_state */
  REQUESTED: "neutral",
  INTAKE: "neutral",
  UNDER_ASSESSMENT: "progress",
  VENDOR_CHECK: "progress",
  PRODUCT_CHECK: "progress",
  PENDING_AUTHORISATION: "progress",
  TREATMENT_PENDING: "progress",
  HELD: "attention",
  AUTHORISED: "positive",
  DEPLOYED: "positive",
  HALTED_PROHIBITED: "halt",
  RETIRED: "terminal",

  /* classification_status */
  PENDING_REVIEW: "progress",
  CHANGES_REQUESTED: "attention",
  /* APPROVED already mapped above (same tone) */
  /* NEEDS_REFRESH already mapped above */

  /* coverage_status */
  OPEN: "neutral",
  PARTIAL: "attention",
  SATISFIED: "positive",

  /* approval_status */
  NOT_STARTED: "neutral",
  UNDER_REVIEW: "progress",
  REJECTED: "halt",
  EXPIRED: "terminal",
  /* APPROVED already mapped above */

  /* eu_ai_act_tier */
  UNCLASSIFIED: "neutral",
  MINIMAL: "neutral",   /* not in §2.2; implementation tone — escalated (V-5) */
  LIMITED: "neutral",   /* not in §2.2; implementation tone — escalated (V-5) */
  REQUIRES_CONTEXT: "attention",
  HIGH: "attention",    /* not in §2.2; implementation tone — escalated (V-5) */
  PROHIBITED: "halt",
};

type ToneStyle = {
  className: string;
  style?: React.CSSProperties;
};

const TONE_STYLES: Record<VerdictTone, ToneStyle> = {
  neutral: {
    className: "border rounded-sm px-2 py-0.5 text-xs font-medium",
    style: { borderColor: "var(--verdict-neutral)", color: "var(--verdict-neutral)" },
  },
  progress: {
    className: "rounded-sm px-2 py-0.5 text-xs font-medium",
    style: {
      backgroundColor: "var(--verdict-progress-fill)",
      color: "var(--verdict-progress-text)",
    },
  },
  positive: {
    className: "rounded-sm px-2 py-0.5 text-xs font-medium",
    style: {
      backgroundColor: "var(--verdict-positive-fill)",
      color: "var(--verdict-positive-text)",
    },
  },
  attention: {
    className: "border rounded-sm px-2 py-0.5 text-xs font-medium",
    style: { borderColor: "var(--verdict-attention)", color: "var(--verdict-attention)" },
  },
  halt: {
    className: "rounded-sm px-2 py-0.5 text-xs font-medium",
    style: {
      backgroundColor: "var(--verdict-halt-fill)",
      color: "var(--verdict-halt-text)",
    },
  },
  terminal: {
    className: "rounded-sm px-2 py-0.5 text-xs font-medium line-through",
    style: { color: "var(--verdict-terminal)" },
  },
};

export function VerdictChip({ value }: { value: string }) {
  const tone = TONE_MAP[value.toUpperCase()];
  if (!tone) {
    return (
      <span
        data-tone="unknown"
        className="rounded-sm border border-dashed px-2 py-0.5 text-xs text-ink-muted"
      >
        {value}
      </span>
    );
  }
  const { className, style } = TONE_STYLES[tone];
  return (
    <span data-tone={tone} className={className} style={style}>
      {value}
    </span>
  );
}

/** Exported for test coverage — guards exhaustiveness against the live V-5 dump. */
export { TONE_MAP };
